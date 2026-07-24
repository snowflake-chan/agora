from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ContentBoost(Base):
    __tablename__ = "content_boosts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    content_id: Mapped[UUID] = mapped_column(
        ForeignKey("content.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # Promotion tier chosen by the user.
    tier: Mapped[str] = mapped_column(String(10), nullable=False)
    # Exposure multiplier applied to feed ranking scores.
    weight: Mapped[float] = mapped_column(nullable=False, default=1.0)
    # Boosts are active for 24 hours from creation.
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
