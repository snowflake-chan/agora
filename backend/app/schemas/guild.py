import uuid
from datetime import datetime

from pydantic import BaseModel


# ── Guild ──

class GuildCreate(BaseModel):
    name: str
    logo: str | None = None
    description: str | None = None


class GuildUpdate(BaseModel):
    name: str | None = None
    logo: str | None = None
    description: str | None = None
    level: int | None = None


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
    joined_at: datetime

    model_config = {"from_attributes": True}


# ── Guild Discussion ──

class GuildDiscussionCreate(BaseModel):
    title: str | None = None
    content: str


class GuildDiscussionRead(BaseModel):
    id: uuid.UUID
    title: str | None = None
    content: str
    author_id: uuid.UUID
    author_username: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}


# ── User guild badge (lightweight) ──

class UserGuildBadge(BaseModel):
    guild_id: uuid.UUID
    guild_name: str
    guild_level: int
    role: str
