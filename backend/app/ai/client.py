import asyncio
import json
import logging
from typing import AsyncIterator, TypeVar
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ValidationError

from app.ai.errors import AIServiceError
from app.ai.prompts import SYSTEM_PROMPT
from app.ai.runtime_config import AIRuntimeConfig, get_ai_runtime_config
from app.ai.schemas import CompletionEnvelope
from app.config import settings


ResponseModel = TypeVar("ResponseModel", bound=BaseModel)
logger = logging.getLogger(__name__)
_provider_semaphore = asyncio.Semaphore(
    min(
        settings.AI_MAX_CONCURRENT_REQUESTS,
        settings.AI_MODERATION_MAX_CONCURRENT_REQUESTS,
    )
)


def _build_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=httpx.Timeout(settings.AI_HTTP_TIMEOUT_SECONDS))


def _is_deepseek_provider(base_url: str) -> bool:
    hostname = (urlparse(base_url).hostname or "").casefold()
    return hostname == "deepseek.com" or hostname.endswith(".deepseek.com")


def _thinking_mode_for(base_url: str) -> str:
    if not _is_deepseek_provider(base_url):
        return ""
    return settings.AI_THINKING_MODE or "disabled"


async def request_structured_completion(
    *,
    user_message: str,
    response_type: type[ResponseModel],
    max_tokens: int,
    system_prompt: str = SYSTEM_PROMPT,
    runtime_config: AIRuntimeConfig | None = None,
) -> ResponseModel:
    """Call an OpenAI-compatible provider without logging sensitive request data."""
    runtime_config = runtime_config or await get_ai_runtime_config()
    url = f"{runtime_config.base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": runtime_config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": settings.AI_TEMPERATURE,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if settings.AI_RESPONSE_FORMAT_ENABLED:
        payload["response_format"] = {"type": "json_object"}
    thinking_mode = _thinking_mode_for(runtime_config.base_url)
    if thinking_mode:
        payload["thinking"] = {"type": thinking_mode}
    headers = {
        "Authorization": f"Bearer {runtime_config.api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with _provider_semaphore:
            async with _build_http_client() as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "AI upstream HTTP failure status=%s",
            exc.response.status_code,
        )
        raise AIServiceError(502, "AI_UPSTREAM_UNAVAILABLE") from exc
    except httpx.RequestError as exc:
        logger.warning("AI upstream transport failure type=%s", type(exc).__name__)
        raise AIServiceError(502, "AI_UPSTREAM_UNAVAILABLE") from exc

    try:
        raw_envelope = response.json()
        choices = raw_envelope.get("choices") if isinstance(raw_envelope, dict) else None
        first_choice = choices[0] if isinstance(choices, list) and choices else None
        finish_reason = (
            first_choice.get("finish_reason")
            if isinstance(first_choice, dict)
            else None
        )
        # Inspect the finish reason before validating message.content. Providers
        # commonly return content=null for a filtered completion.
        if finish_reason == "content_filter":
            raise AIServiceError(422, "AI_PROVIDER_FILTERED")
        if finish_reason != "stop":
            raise AIServiceError(502, "AI_UPSTREAM_INVALID_RESPONSE")
        envelope = CompletionEnvelope.model_validate(raw_envelope, strict=True)
        choice = envelope.choices[0]
        return response_type.model_validate_json(
            choice.message.content,
            strict=True,
        )
    except AIServiceError:
        raise
    except (ValueError, ValidationError, TypeError, IndexError) as exc:
        raise AIServiceError(502, "AI_UPSTREAM_INVALID_RESPONSE") from exc


async def stream_structured_completion(
    *,
    user_message: str,
    max_tokens: int,
    system_prompt: str = SYSTEM_PROMPT,
    runtime_config: AIRuntimeConfig | None = None,
) -> AsyncIterator[str]:
    """Yield content deltas from an OpenAI-compatible streaming completion."""
    runtime_config = runtime_config or await get_ai_runtime_config()
    url = f"{runtime_config.base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": runtime_config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": settings.AI_TEMPERATURE,
        "max_tokens": max_tokens,
        "stream": True,
    }
    if settings.AI_RESPONSE_FORMAT_ENABLED:
        payload["response_format"] = {"type": "json_object"}
    thinking_mode = _thinking_mode_for(runtime_config.base_url)
    if thinking_mode:
        payload["thinking"] = {"type": thinking_mode}
    headers = {
        "Authorization": f"Bearer {runtime_config.api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    try:
        async with _provider_semaphore:
            async with _build_http_client() as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line or line.startswith(":"):
                            continue
                        data = line[5:].strip() if line.startswith("data:") else line.strip()
                        if data == "[DONE]":
                            break
                        try:
                            event = json.loads(data)
                        except (ValueError, TypeError):
                            raise AIServiceError(502, "AI_UPSTREAM_INVALID_RESPONSE")
                        choices = event.get("choices") if isinstance(event, dict) else None
                        choice = choices[0] if isinstance(choices, list) and choices else None
                        delta = choice.get("delta") if isinstance(choice, dict) else None
                        content = delta.get("content") if isinstance(delta, dict) else None
                        if isinstance(content, str) and content:
                            yield content
                        finish_reason = choice.get("finish_reason") if isinstance(choice, dict) else None
                        if finish_reason == "content_filter":
                            raise AIServiceError(422, "AI_PROVIDER_FILTERED")
                        if finish_reason not in (None, "stop"):
                            raise AIServiceError(502, "AI_UPSTREAM_INVALID_RESPONSE")
    except AIServiceError:
        raise
    except httpx.HTTPStatusError as exc:
        logger.warning("AI upstream streaming HTTP failure status=%s", exc.response.status_code)
        raise AIServiceError(502, "AI_UPSTREAM_UNAVAILABLE") from exc
    except httpx.RequestError as exc:
        logger.warning("AI upstream streaming transport failure type=%s", type(exc).__name__)
        raise AIServiceError(502, "AI_UPSTREAM_UNAVAILABLE") from exc
