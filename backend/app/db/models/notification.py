from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Notification(Base):
    __tablename__ = "notification"
    __table_args__ = (
        Index(
            "uq_notification_dedupe_key",
            "dedupe_key",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    recipient_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str] = mapped_column(String(500), nullable=False)
    dedupe_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now, nullable=False
    )

    # ── Relationships ──
    recipient: Mapped["User"] = relationship("User", lazy="joined")  # type: ignore[name-defined]
