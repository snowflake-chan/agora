from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PointTransaction(Base):
    """Immutable audit log for every point change."""
    __tablename__ = "point_transaction"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    guild_id: Mapped[UUID | None] = mapped_column(ForeignKey("guild.id", ondelete="SET NULL"), nullable=True, index=True)
    patch_id: Mapped[UUID | None] = mapped_column(ForeignKey("patch.id", ondelete="SET NULL"), nullable=True, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(50), nullable=False)  # "patch_merged", "first_guild_credit"
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now, nullable=False
    )