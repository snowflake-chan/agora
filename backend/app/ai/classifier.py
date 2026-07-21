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


async def require_trusted_local_classification(texts: list[str]) -> None:
    """Fail closed unless the trusted pre-egress classifier clears every value."""
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
    if any(status != "non_political" for status in envelope.statuses):
        raise AIServiceError(422, "POLITICAL_CONTENT_UNAVAILABLE")
