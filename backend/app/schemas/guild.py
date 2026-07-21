import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# ── Guild ──

class GuildCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    logo: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("GUILD_NAME_REQUIRED")
        return normalized

    @field_validator("logo", "description", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None


class GuildUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    logo: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=2000)
    level: int | None = Field(default=None, ge=1, le=5)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("GUILD_NAME_REQUIRED")
        return normalized

    @field_validator("logo", "description", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None


class GuildRead(BaseModel):
    id: uuid.UUID
    name: str
    logo: str | None = None
    description: str | None = None
    president_id: uuid.UUID
    president_username: str = ""
    member_count: int = 0
    level: int = 1
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Guild Member ──

class GuildMemberRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    username: str = ""
    nickname: str | None = None
    role: str
    status: str = "approved"
    joined_at: datetime

    model_config = {"from_attributes": True}


# ── Guild Discussion ──

class GuildDiscussionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    content: str = Field(min_length=1, max_length=20_000)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("GUILD_DISCUSSION_REQUIRED")
        return normalized

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None


class GuildDiscussionRead(BaseModel):
    id: uuid.UUID
    title: str | None = None
    content: str
    author_id: uuid.UUID
    author_username: str = ""
    moderation_status: str = "published"
    moderation_reason: str | None = None
    moderation_review_note: str | None = None
    revision_number: int = 1
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── User guild badge (lightweight) ──

class UserGuildBadge(BaseModel):
    guild_id: uuid.UUID
    guild_name: str
    guild_level: int
    role: str
