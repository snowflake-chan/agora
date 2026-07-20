from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text, Boolean, Integer
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Report(Base):
    __tablename__ = "report"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    content_id: Mapped[UUID | None] = mapped_column(ForeignKey("content.id", ondelete="SET NULL"), index=True, nullable=True)
    reporter_id: Mapped[UUID] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending / resolved / dismissed
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.now)

    reporter: Mapped["User"] = relationship("User", lazy="joined")  # type: ignore[name-defined]
    content: Mapped["Content"] = relationship("Content", lazy="joined")  # type: ignore[name-defined]


class BanRecord(Base):
    __tablename__ = "ban_record"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    target_user_id: Mapped[UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    content_id: Mapped[UUID | None] = mapped_column(ForeignKey("content.id", ondelete="SET NULL"), nullable=True)
    type: Mapped[str] = mapped_column(String(20))  # "ban_user" | "mute_post" | "mute_patch"
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)  # null = permanent
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.now)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    target_user: Mapped["User"] = relationship("User", lazy="joined")  # type: ignore[name-defined]
