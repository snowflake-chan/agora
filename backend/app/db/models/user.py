from datetime import datetime, timezone

from sqlalchemy import String
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

    # Relationships
    token_balance: Mapped["TokenBalance"] = relationship(  # type: ignore[name-defined]
        "TokenBalance",
        back_populates="user",
        uselist=False,
        primaryjoin="User.id == foreign(TokenBalance.user_id)",
    )


async def get_user_db(session: AsyncSession = Depends(get_session)):
    yield SQLAlchemyUserDatabase(session, User)
