"""Token snapshot model for monetary policy tracking."""

from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Date, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TokenSnapshot(Base):
    __tablename__ = "token_snapshots"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4())
    )
    snapshot_date: Mapped[date] = mapped_column(
        Date, unique=True, nullable=False, index=True
    )
    circulating_supply: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_issued: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_burned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active_users: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    transaction_count_24h: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
