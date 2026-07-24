from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, String, Float, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Vote(Base):
    __tablename__ = "vote"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patch_id: Mapped[UUID] = mapped_column(
        ForeignKey("patch.id", ondelete="CASCADE"), index=True, nullable=False
    )
    voter_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    choice: Mapped[str] = mapped_column(String(10), nullable=False)
    # Token-weighted voting: AGC consumed to boost vote weight (NOT returned)
    stake_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now, onupdate=datetime.now, nullable=False
    )

    # ── Relationships ──
    patch: Mapped["Patch"] = relationship("Patch", back_populates="votes")  # type: ignore[name-defined]
    voter: Mapped["User"] = relationship("User", lazy="joined")  # type: ignore[name-defined]

    __table_args__ = (
        UniqueConstraint("patch_id", "voter_id", name="uq_patch_voter"),
    )
