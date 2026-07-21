from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app import content_moderation
from app.config import settings
from app.schemas.guild import GuildDiscussionCreate
from app.schemas.post import CommentCreate, PostCreate, PostUpdate


def _assert_ai_input_too_long(factory) -> None:
    with pytest.raises(ValidationError) as error:
        factory()
    assert "AI_INPUT_TOO_LONG" in str(error.value)


def test_publication_schemas_reject_combined_ai_input_before_routes(monkeypatch):
    monkeypatch.setattr(settings, "AI_MAX_INPUT_CHARS", 20)

    _assert_ai_input_too_long(
        lambda: PostCreate(
            title="1234567890",
            content="1234567890",
            tags=["x"],
        )
    )
    _assert_ai_input_too_long(
        lambda: PostCreate(
            title="Title",
            content="Body",
            poll={
                "question": "Which option is best?",
                "options": ["One", "Two"],
                "duration_hours": 24,
            },
        )
    )
    _assert_ai_input_too_long(
        lambda: CommentCreate(content="x" * 21)
    )
    _assert_ai_input_too_long(
        lambda: GuildDiscussionCreate(title="12345", content="x" * 16)
    )
    _assert_ai_input_too_long(
        lambda: PostUpdate(revision_number=1, content="x" * 21)
    )


def test_publication_schema_accepts_exact_ai_input_boundary(monkeypatch):
    monkeypatch.setattr(settings, "AI_MAX_INPUT_CHARS", 20)

    post = PostCreate(title="1234567890", content="1234567890")

    assert post.title == "1234567890"
    assert post.content == "1234567890"


@pytest.mark.asyncio
async def test_semantic_review_starts_after_read_transaction_commit(monkeypatch):
    events = []

    class Session:
        async def commit(self):
            events.append("commit")

    async def fake_assess(*texts):
        events.append(("assess", texts))
        return SimpleNamespace(status="published", reason=None)

    monkeypatch.setattr(
        content_moderation,
        "assess_content_moderation",
        fake_assess,
    )

    result = await content_moderation.assess_content_moderation_after_read(
        Session(),
        "Title",
        "Body",
    )

    assert result.status == "published"
    assert events == ["commit", ("assess", ("Title", "Body"))]
