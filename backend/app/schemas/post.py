from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


# ── Post ──

class PostRead(BaseModel):
    id: UUID
    title: str
    content: str
    author_id: UUID
    tags: list[str] | None
    author_username: str | None = None
    reply_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PostCreate(BaseModel):
    title: str
    content: str
    tags: list[str] | None = None


class PostUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None


# ── Comment ──

class CommentRead(BaseModel):
    id: UUID
    content: str
    author_id: UUID
    parent_id: UUID
    replying_id: UUID | None
    author_username: str | None = None
    replying_to_username: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CommentCreate(BaseModel):
    content: str
    replying_id: UUID | None = None
