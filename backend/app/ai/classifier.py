import logging
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.ai.errors import AIServiceError
from app.config import settings


PoliticalStatus = Literal["non_political", "political", "uncertain"]
logger = logging.getLogger(__name__)


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


async def require_trusted_local_classification(
    texts: list[str],
    *,
    block_uncertain: bool = True,
    source_moderation_reason: str | None = None,
    source_moderation_provenance: str | None = None,
) -> None:
    """Fail closed unless the trusted pre-egress classifier clears every value."""
    related_texts = combine_related_texts(texts)
    if not related_texts:
        return
    statuses = await classify_with_trusted_local_service(related_texts)
    blocked = any(
        status == "political" or (block_uncertain and status == "uncertain")
        for status in statuses
    )
    if blocked:
        raise AIServiceError(
            422,
            "POLITICAL_CONTENT_UNAVAILABLE",
            source_moderation_reason=source_moderation_reason,
            source_moderation_provenance=source_moderation_provenance,
        )
