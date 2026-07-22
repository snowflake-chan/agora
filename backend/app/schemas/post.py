from datetime import datetime
import hashlib
import unicodedata
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.content_input import validate_moderation_input_size


def normalize_poll_option(value: str) -> str:
    """Normalize option text for storage and case-insensitive uniqueness."""
    return " ".join(value.split())


def poll_option_key(value: str) -> str:
    return unicodedata.normalize("NFKC", normalize_poll_option(value)).casefold()


def poll_option_digest(value: str) -> str:
    return hashlib.sha256(poll_option_key(value).encode("utf-8")).hexdigest()


class PollCreate(BaseModel):
    question: str
    options: list[str] = Field(min_length=2, max_length=6)
    duration_hours: int = Field(ge=24, le=720)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        normalized = value.strip()
        if not 5 <= len(normalized) <= 160:
            raise ValueError("Poll questions must be 5 to 160 characters")
        return normalized

    @field_validator("options")
    @classmethod
    def normalize_options(cls, values: list[str]) -> list[str]:
        normalized = [normalize_poll_option(value) for value in values]
        if any(not 1 <= len(value) <= 80 for value in normalized):
            raise ValueError("Poll options must be 1 to 80 characters")
        keys = [poll_option_key(value) for value in normalized]
        if len(keys) != len(set(keys)):
            raise ValueError("Poll options must be unique")
        return normalized


class PollOptionRead(BaseModel):
    id: UUID
    text: str
    vote_count: int


class PollRead(BaseModel):
    id: UUID
    question: str
    closes_at: datetime
    is_closed: bool
    total_votes: int
    options: list[PollOptionRead]
    selected_option_id: UUID | None = None


class PollVoteCreate(BaseModel):
    option_id: UUID


# ── Post ──

class PostRead(BaseModel):
    id: UUID
    title: str
    content: str
    author_id: UUID
    tags: list[str] | None
    author_username: str | None = None
    reply_count: int = 0
    like_count: int = 0
    liked_by_me: bool = False
    poll: PollRead | None = None
    moderation_status: str = "published"
    moderation_reason: str | None = None
    moderation_review_note: str | None = None
    revision_number: int = 1
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PostCreate(BaseModel):
    title: str = Field(max_length=200)
    content: str
    tags: list[str] | None = Field(default=None, max_length=20)
    poll: PollCreate | None = None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        normalized = [value.strip() for value in values]
        if any(len(value) > 50 for value in normalized):
            raise ValueError("TAG_TOO_LONG")
        return normalized

    @model_validator(mode="after")
    def validate_ai_input_size(self):
        texts = [self.title, self.content, *(self.tags or [])]
        if self.poll is not None:
            texts.extend([self.poll.question, *self.poll.options])
        validate_moderation_input_size(texts)
        return self


class PostUpdate(BaseModel):
    revision_number: int = Field(ge=1)
    title: str | None = Field(default=None, max_length=200)
    content: str | None = None
    tags: list[str] | None = Field(default=None, max_length=20)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        normalized = [value.strip() for value in values]
        if any(len(value) > 50 for value in normalized):
            raise ValueError("TAG_TOO_LONG")
        return normalized

    @model_validator(mode="after")
    def validate_ai_input_size(self):
        validate_moderation_input_size(
            [self.title, self.content, *(self.tags or [])]
        )
        return self


class ContentEditRead(BaseModel):
    id: UUID
    type: str
    title: str | None = None
    content: str
    tags: list[str] | None = None
    author_id: UUID
    parent_id: UUID | None = None
    patch_id: UUID | None = None
    guild_id: UUID | None = None
    moderation_status: str
    moderation_reason: str | None = None
    moderation_review_note: str | None = None
    revision_number: int
    created_at: datetime
    updated_at: datetime


class ContentRevisionRead(BaseModel):
    id: UUID
    content_id: UUID
    version: int
    title: str | None = None
    content: str
    tags: list[str] | None = None
    editor_id: UUID
    edited_at: datetime

    model_config = {"from_attributes": True}


class PostLikeRead(BaseModel):
    like_count: int
    liked_by_me: bool


# ── Comment ──

class CommentRead(BaseModel):
    id: UUID
    content: str
    author_id: UUID
    parent_id: UUID
    replying_id: UUID | None
    author_username: str | None = None
    replying_to_username: str | None = None
    replying_to_content: str | None = None
    reply_count: int = 0
    like_count: int = 0
    liked_by_me: bool = False
    moderation_status: str = "published"
    moderation_reason: str | None = None
    moderation_review_note: str | None = None
    revision_number: int = 1
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class CommentCreate(BaseModel):
    content: str
    replying_id: UUID | None = None

    @model_validator(mode="after")
    def validate_ai_input_size(self):
        validate_moderation_input_size([self.content])
        return self


# ── Feed (unified timeline) ──

class FeedItem(BaseModel):
    id: UUID
    type: str  # "post" | "patch"
    title: str
    content: str
    author_id: UUID
    author_username: str | None = None
    created_at: datetime

    # Post-specific
    tags: list[str] | None = None
    reply_count: int = 0
    like_count: int = 0
    poll: PollRead | None = None
    moderation_status: str = "published"
    moderation_reason: str | None = None
    moderation_review_note: str | None = None
    revision_number: int = 1

    # Patch-specific
    pr_number: int | None = None
    status: str | None = None
    voting_started_at: datetime | None = None
    voting_ends_at: datetime | None = None
    voting_period_hours: int | None = None
    voting_window_kind: str | None = None
    for_count: int = 0
    against_count: int = 0
    abstain_count: int = 0

    # Promotion boost applied to feed ranking
    boost_weight: float = 1.0

    # Ranking explanation
    ranking_reason: str | None = None


class ContentBoostCreate(BaseModel):
    tier: str  # "low" | "mid" | "high"
