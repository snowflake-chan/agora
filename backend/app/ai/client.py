import logging
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.ai.errors import AIServiceError
from app.ai.prompts import SYSTEM_PROMPT
from app.ai.schemas import CompletionEnvelope
from app.config import settings


ResponseModel = TypeVar("ResponseModel", bound=BaseModel)
logger = logging.getLogger(__name__)


def _build_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=httpx.Timeout(settings.AI_HTTP_TIMEOUT_SECONDS))


async def request_structured_completion(
    *,
    user_message: str,
    response_type: type[ResponseModel],
    max_tokens: int,
) -> ResponseModel:
    """Call DeepSeek without logging credentials, source text, or provider details."""
    url = f"{settings.resolved_ai_base_url().rstrip('/')}/chat/completions"
    payload = {
        "model": settings.resolved_ai_model(),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "thinking": {"type": "disabled"},
        "response_format": {"type": "json_object"},
        "max_tokens": max_tokens,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {settings.resolved_ai_api_key()}",
        "Content-Type": "application/json",
    }

    try:
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
        envelope = CompletionEnvelope.model_validate(response.json(), strict=True)
        choice = envelope.choices[0]
        if choice.finish_reason == "content_filter":
            # The provider does not say whether it filtered the source or its own
            # generated output. Do not mutate the source content on this signal.
            raise AIServiceError(422, "AI_PROVIDER_FILTERED")
        if choice.finish_reason != "stop":
            raise AIServiceError(502, "AI_UPSTREAM_INVALID_RESPONSE")
        return response_type.model_validate_json(
            choice.message.content,
            strict=True,
        )
    except AIServiceError:
        raise
    except (ValueError, ValidationError, TypeError, IndexError) as exc:
        raise AIServiceError(502, "AI_UPSTREAM_INVALID_RESPONSE") from exc
