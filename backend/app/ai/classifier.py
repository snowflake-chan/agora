import asyncio
import logging
from dataclasses import dataclass
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.ai.errors import AIServiceError
from app.ai.client import request_structured_completion
from app.ai.prompts import MODERATION_SYSTEM_PROMPT, build_moderation_message
from app.ai.runtime_config import AIRuntimeConfig, get_ai_runtime_config
from app.ai.schemas import ModerationAIResponse
from app.config import settings


PoliticalStatus = Literal["non_political", "political", "uncertain"]
logger = logging.getLogger(__name__)
_local_classifier_semaphore = asyncio.Semaphore(
    settings.AI_MODERATION_MAX_CONCURRENT_REQUESTS
)


@dataclass(frozen=True, slots=True)
class SemanticModerationDecision:
    status: PoliticalStatus
    provenance: str
    cached: bool = False


class ClassificationEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    statuses: list[PoliticalStatus] = Field(min_length=1)


def _build_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(settings.AI_POLITICAL_CLASSIFIER_TIMEOUT_SECONDS)
    )


async def classify_with_trusted_local_service(
    texts: list[str],
) -> list[PoliticalStatus]:
    """Return trusted local classifications without exposing source text in logs."""
    url = settings.AI_POLITICAL_CLASSIFIER_URL.strip()
    if not url:
        raise AIServiceError(503, "AI_POLITICAL_GUARD_UNAVAILABLE")

    try:
        async with _build_http_client() as client:
            response = await client.post(url, json={"texts": texts})
            response.raise_for_status()
        envelope = ClassificationEnvelope.model_validate(response.json(), strict=True)
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Local political classifier HTTP failure status=%s",
            exc.response.status_code,
        )
        raise AIServiceError(503, "AI_POLITICAL_GUARD_UNAVAILABLE") from exc
    except httpx.RequestError as exc:
        logger.warning(
            "Local political classifier transport failure type=%s",
            type(exc).__name__,
        )
        raise AIServiceError(503, "AI_POLITICAL_GUARD_UNAVAILABLE") from exc
    except (ValueError, ValidationError, TypeError) as exc:
        raise AIServiceError(503, "AI_POLITICAL_GUARD_UNAVAILABLE") from exc

    if len(envelope.statuses) != len(texts):
        raise AIServiceError(503, "AI_POLITICAL_GUARD_UNAVAILABLE")
    return envelope.statuses


def combine_related_texts(texts: list[str]) -> list[str]:
    """Classify related fields as one document instead of ambiguous fragments."""
    values = [text.strip() for text in texts if text and text.strip()]
    return ["\n\n".join(values)] if values else []


def _provider_fallback_is_available(runtime_config: AIRuntimeConfig) -> bool:
    return (
        runtime_config.moderation_provider_fallback_enabled
        and runtime_config.provider_is_configured()
    )


def semantic_moderation_is_configured(runtime_config: AIRuntimeConfig) -> bool:
    return bool(
        settings.AI_POLITICAL_CLASSIFIER_URL.strip()
        or _provider_fallback_is_available(runtime_config)
    )


def _moderation_engine(runtime_config: AIRuntimeConfig) -> tuple[str, str]:
    classifier_url = settings.AI_POLITICAL_CLASSIFIER_URL.strip()
    if classifier_url:
        return f"trusted-local:{classifier_url}", "trusted_classifier"
    if _provider_fallback_is_available(runtime_config):
        return f"provider:{runtime_config.model}", "provider"
    raise AIServiceError(503, "AI_POLITICAL_GUARD_UNAVAILABLE")


async def classify_semantic_content(
    texts: list[str],
) -> SemanticModerationDecision:
    """Classify related fields as one semantic document with a hashed verdict cache."""
    # Import lazily: notifications package initialization reaches content moderation.
    from app.ai.storage import (
        cache_moderation,
        cache_fill_lock,
        enforce_ai_moderation_rate_limit,
        get_cached_moderation,
        moderation_cache_key,
    )

    runtime_config = await get_ai_runtime_config()
    related_texts = combine_related_texts(texts)
    if not related_texts:
        return SemanticModerationDecision(
            status="non_political",
            provenance="trusted_classifier",
            cached=True,
        )

    document = related_texts[0]
    engine, provenance = _moderation_engine(runtime_config)
    cache_key = moderation_cache_key(text=document, engine=engine)
    cached = await get_cached_moderation(cache_key)
    if cached is not None:
        status, cached_provenance = cached
        return SemanticModerationDecision(
            status=status,
            provenance=cached_provenance,
            cached=True,
        )

    async with cache_fill_lock(cache_key):
        # Another coroutine or process may have filled the cache after our first
        # read. Recheck before consuming review capacity or provider budget.
        cached = await get_cached_moderation(cache_key)
        if cached is not None:
            status, cached_provenance = cached
            return SemanticModerationDecision(
                status=status,
                provenance=cached_provenance,
                cached=True,
            )

        await enforce_ai_moderation_rate_limit(
            provider_fallback=provenance == "provider"
        )
        if provenance == "trusted_classifier":
            try:
                async with _local_classifier_semaphore:
                    statuses = await classify_with_trusted_local_service([document])
                status = statuses[0]
            except AIServiceError:
                if not _provider_fallback_is_available(runtime_config):
                    raise
                provider_engine = f"provider:{runtime_config.model}"
                provider_cache_key = moderation_cache_key(
                    text=document,
                    engine=provider_engine,
                )
                provider_cached = await get_cached_moderation(provider_cache_key)
                if provider_cached is not None:
                    status, cached_provenance = provider_cached
                    return SemanticModerationDecision(
                        status=status,
                        provenance=cached_provenance,
                        cached=True,
                    )
                await enforce_ai_moderation_rate_limit(provider_fallback=True)
                try:
                    result = await request_structured_completion(
                        user_message=build_moderation_message(document),
                        response_type=ModerationAIResponse,
                        max_tokens=24,
                        system_prompt=MODERATION_SYSTEM_PROMPT,
                        runtime_config=runtime_config,
                    )
                except AIServiceError as exc:
                    raise AIServiceError(
                        503,
                        "AI_POLITICAL_GUARD_UNAVAILABLE",
                    ) from exc
                status = result.political_status
                provenance = "provider"
                cache_key = provider_cache_key
        else:
            try:
                result = await request_structured_completion(
                    user_message=build_moderation_message(document),
                    response_type=ModerationAIResponse,
                    max_tokens=24,
                    system_prompt=MODERATION_SYSTEM_PROMPT,
                    runtime_config=runtime_config,
                )
            except AIServiceError as exc:
                raise AIServiceError(
                    503,
                    "AI_POLITICAL_GUARD_UNAVAILABLE",
                ) from exc
            status = result.political_status

        await cache_moderation(
            cache_key,
            status=status,
            provenance=provenance,
        )
    return SemanticModerationDecision(
        status=status,
        provenance=provenance,
    )


async def require_semantic_classification(
    texts: list[str],
    *,
    block_uncertain: bool = True,
    source_moderation_reason: str | None = None,
) -> SemanticModerationDecision:
    """Fail closed on semantic political or uncertain content."""
    decision = await classify_semantic_content(texts)
    blocked = decision.status == "political" or (
        block_uncertain and decision.status == "uncertain"
    )
    if blocked:
        raise AIServiceError(
            422,
            "POLITICAL_CONTENT_UNAVAILABLE",
            source_moderation_reason=source_moderation_reason,
            source_moderation_provenance=decision.provenance,
        )
    return decision
