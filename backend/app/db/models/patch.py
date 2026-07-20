from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Patch(Base):
    __tablename__ = "patch"
    __table_args__ = (
        Index(
            "uq_patch_active_pr_number",
            "pr_number",
            unique=True,
            postgresql_where=text("status IN ('draft', 'voting', 'passed')"),
        ),
        Index(
            "ix_patch_author_merged_updated_at",
            "author_id",
            "updated_at",
            postgresql_where=text("status = 'merged'"),
        ),
        CheckConstraint(
            """
            (
                status != 'voting'
                AND
                voting_ends_at IS NULL
                AND voting_started_at IS NULL
                AND voting_period_hours IS NULL
                AND voting_window_kind IS NULL
            )
            OR
            (
                status != 'draft'
                AND
                voting_ends_at IS NOT NULL
                AND voting_started_at IS NOT NULL
                AND voting_period_hours IS NOT NULL
                AND voting_window_kind IS NOT NULL
                AND voting_ends_at = (
                    voting_started_at + voting_period_hours * INTERVAL '1 hour'
                )
                AND (
                    (voting_window_kind = 'standard' AND voting_period_hours = 72)
                    OR
                    (voting_window_kind = 'active_creator' AND voting_period_hours = 24)
                )
            )
            """,
            name="ck_patch_voting_window_snapshot",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    pr_number: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    voting_ends_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    voting_started_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    voting_period_hours: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True
    )
    voting_window_kind: Mapped[str | None] = mapped_column(
        String(24), nullable=True
    )
    author_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now, onupdate=datetime.now, nullable=False
    )

    # ── Relationships ──
    author: Mapped["User"] = relationship("User", lazy="joined")  # type: ignore[name-defined]
    votes: Mapped[list["Vote"]] = relationship("Vote", back_populates="patch", lazy="selectin", cascade="all, delete-orphan")  # type: ignore[name-defined]
