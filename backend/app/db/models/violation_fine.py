"""Violation fine system: admin-issued fines for rule violations."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ViolationFine(Base):
    """A fine issued to a user for violating community rules."""

    __tablename__ = "violation_fines"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    # What the fine is associated with
    reference_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "post" | "comment" | "patch" | "general"
    reference_id: Mapped[UUID | None] = mapped_column(nullable=True)
    # Who issued the fine
    issued_by: Mapped[UUID] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # "pending" | "paid" | "cancelled"
    issued_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )