from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


# ── Patch ──

class PatchRead(BaseModel):
    id: UUID
    title: str
    content: str
    pr_number: int
    status: str
    author_id: UUID
    author_username: str | None = None
    for_count: int = 0
    against_count: int = 0
    abstain_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PatchCreate(BaseModel):
    title: str
    content: str
    pr_number: int


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
