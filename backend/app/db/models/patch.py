from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, SmallInteger, String, Text, UniqueConstraint, text
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
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    pr_number: Mapped[int] = mapped_column(nullable=False)
    submitted_head_sha: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    revision_number: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
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
    revisions: Mapped[list["PatchRevision"]] = relationship(
        "PatchRevision",
        back_populates="patch",
        order_by="PatchRevision.version",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )


class PatchRevision(Base):
    """Immutable snapshot of a draft proposal superseded by an edit."""

    __tablename__ = "patch_revision"
    __table_args__ = (
        UniqueConstraint(
            "patch_id", "version", name="uq_patch_revision_version"
        ),
        CheckConstraint("version > 0", name="ck_patch_revision_version_positive"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    patch_id: Mapped[UUID] = mapped_column(
        ForeignKey("patch.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    editor_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    edited_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now, nullable=False
    )

    patch: Mapped[Patch] = relationship(Patch, back_populates="revisions")
