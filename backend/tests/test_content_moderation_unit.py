import pytest

from app.ai.errors import AIServiceError
from app.config import settings
from app import content_moderation


@pytest.mark.asyncio
async def test_trusted_classifier_marks_semantic_political_content(monkeypatch):
    monkeypatch.setattr(
        settings,
        "AI_POLITICAL_CLASSIFIER_URL",
        "http://politics-classifier:8080/classify",
    )

    async def classify(_texts):
        return ["political"]

    monkeypatch.setattr(
        content_moderation,
        "classify_with_trusted_local_service",
        classify,
    )
    result = await content_moderation.assess_content_moderation(
        "A semantically sensitive sentence without keyword matches."
    )
    assert result.status == "pending_review"
    assert result.reason == "political_or_uncertain"


@pytest.mark.asyncio
async def test_configured_classifier_failure_is_held_for_review(monkeypatch):
    monkeypatch.setattr(
        settings,
        "AI_POLITICAL_CLASSIFIER_URL",
        "http://politics-classifier:8080/classify",
    )

    async def unavailable(_texts):
        raise AIServiceError(503, "AI_POLITICAL_GUARD_UNAVAILABLE")

    monkeypatch.setattr(
        content_moderation,
        "classify_with_trusted_local_service",
        unavailable,
    )
    result = await content_moderation.assess_content_moderation(
        "An otherwise ordinary sentence."
    )
    assert result.status == "pending_review"
    assert result.reason == "classifier_unavailable"
