import uuid
from pydantic import BaseModel, EmailStr


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    nickname: str | None
    bio: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class UserPublic(BaseModel):
    """Public profile – no email exposed."""
    id: uuid.UUID
    username: str
    nickname: str | None
    bio: str | None = None

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    username: str | None = None
    nickname: str | None = None
    bio: str | None = None
    password: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

