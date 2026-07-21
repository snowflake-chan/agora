from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Patch ──

class PatchRead(BaseModel):
    id: UUID
    title: str
    content: str
    pr_number: int
    status: str
    author_id: UUID
    author_username: str | None = None
    voting_started_at: datetime | None = None
    voting_ends_at: datetime | None = None
    voting_period_hours: int | None = None
    voting_window_kind: str | None = None
    for_count: int = 0
    against_count: int = 0
    abstain_count: int = 0
    comment_count: int = 0
    revision_number: int = 1
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PatchCreate(BaseModel):
    title: str
    content: str
    pr_number: int
    submitted_head_sha: str | None = None


class PatchUpdate(BaseModel):
    revision_number: int = Field(ge=1)
    title: str | None = None
    content: str | None = None


class PatchRevisionRead(BaseModel):
    id: UUID
    patch_id: UUID
    version: int
    title: str
    content: str
    editor_id: UUID
    edited_at: datetime

    model_config = {"from_attributes": True}


# ── Vote ──

class VoteRead(BaseModel):
    id: UUID
    patch_id: UUID
    voter_id: UUID
    choice: str
    voter_username: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class VoteCreate(BaseModel):
    choice: str = "for"  # "for", "against", "abstain"
