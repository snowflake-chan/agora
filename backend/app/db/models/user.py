from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import TIMESTAMP


from fastapi_users.db import SQLAlchemyBaseUserTableUUID, SQLAlchemyUserDatabase
from fastapi import Depends

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column, relationship

from app.db.base import Base
from app.db import get_session

class User(SQLAlchemyBaseUserTableUUID, Base):
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bio: Mapped[str | None] = mapped_column(String(500), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    first_guild_id: Mapped[UUID | None] = mapped_column(ForeignKey("guild.id", ondelete="SET NULL"), nullable=True)

    # Relationships


async def get_user_db(session: AsyncSession = Depends(get_session)):
    yield SQLAlchemyUserDatabase(session, User)
