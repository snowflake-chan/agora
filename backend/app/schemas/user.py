import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    nickname: str | None
    bio: str | None = None
    role: str = "user"
    is_active: bool
    points: int = 0
    first_guild_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class UserPublic(BaseModel):
    """Public profile – no email exposed."""
    id: uuid.UUID
    username: str
    nickname: str | None
    bio: str | None = None
    follower_count: int = 0
    following_count: int = 0
    is_following: bool = False
    points: int = 0
    first_guild_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    username: str | None = Field(default=None, min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_]+$")
    nickname: str | None = None
    bio: str | None = None
    password: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class FollowState(BaseModel):
    follower_count: int
    following_count: int
    is_following: bool


class UserContentItem(BaseModel):
    id: uuid.UUID
    type: str
    title: str | None = None
    content: str
    created_at: datetime
    root_type: str | None = None
    root_id: uuid.UUID | None = None
    root_title: str | None = None
    replying_to_id: uuid.UUID | None = None
    replying_to_username: str | None = None
    replying_to_content: str | None = None
    reply_count: int = 0
    like_count: int = 0
    pr_number: int | None = None
    status: str | None = None
    voting_started_at: datetime | None = None
    voting_ends_at: datetime | None = None
    voting_period_hours: int | None = None
    voting_window_kind: str | None = None
    can_delete: bool = False
    moderation_status: str = "published"
    moderation_reason: str | None = None
    moderation_review_note: str | None = None

