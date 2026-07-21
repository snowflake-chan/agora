from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Content(Base):
    __tablename__ = "content"
    __table_args__ = (
        CheckConstraint(
            "moderation_status IN "
            "('published', 'pending_review', 'approved', 'rejected')",
            name="ck_content_moderation_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    type: Mapped[str] = mapped_column(String(20))  # "post" | "comment"
    title: Mapped[str | None] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    author_id: Mapped[UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("content.id", ondelete="CASCADE"), index=True
    )
    patch_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("patch.id", ondelete="CASCADE"), index=True, nullable=True
    )
    replying_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("content.id", ondelete="SET NULL"), index=True, nullable=True
    )
    guild_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("guild.id", ondelete="CASCADE"), index=True, nullable=True
    )
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)))
    revision_number: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    moderation_status: Mapped[str] = mapped_column(
        String(24), default="published", nullable=False, index=True
    )
    moderation_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    moderation_review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    moderation_reviewed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    moderation_reviewed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    moderation_effects_completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now, onupdate=datetime.now, nullable=False
    )

    # ── Parent post (via parent_id) ──
    parent: Mapped["Content | None"] = relationship(
        "Content", remote_side="Content.id", back_populates="replies",
        foreign_keys=parent_id, lazy="joined"
    )
    replies: Mapped[list["Content"]] = relationship(
        "Content", back_populates="parent",
        foreign_keys=parent_id, lazy="selectin"
    )

    # ── Replying to marker (via replying_id) ──
    replying_to: Mapped["Content | None"] = relationship(
        "Content", remote_side="Content.id", back_populates="replied_by",
        foreign_keys=replying_id, lazy="joined"
    )
    replied_by: Mapped[list["Content"]] = relationship(
        "Content", back_populates="replying_to",
        foreign_keys=replying_id, lazy="selectin"
    )

    # ── Author ──
    author: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User",
        foreign_keys=[author_id],
        lazy="joined",
    )
    moderation_reviewer: Mapped["User | None"] = relationship(  # type: ignore[name-defined]
        "User",
        foreign_keys=[moderation_reviewed_by],
        lazy="raise",
    )
    poll: Mapped["PostPoll | None"] = relationship(  # type: ignore[name-defined]
        "PostPoll",
        back_populates="post",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )
    revisions: Mapped[list["ContentRevision"]] = relationship(
        "ContentRevision",
        back_populates="content_item",
        order_by="ContentRevision.version",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )


class ContentRevision(Base):
    """Immutable snapshot of a content version superseded by an edit."""

    __tablename__ = "content_revision"
    __table_args__ = (
        UniqueConstraint(
            "content_id", "version", name="uq_content_revision_version"
        ),
        CheckConstraint("version > 0", name="ck_content_revision_version_positive"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    content_id: Mapped[UUID] = mapped_column(
        ForeignKey("content.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)), nullable=True)
    editor_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    was_public: Mapped[bool] = mapped_column(Boolean, nullable=False)
    edited_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now, nullable=False
    )

    content_item: Mapped[Content] = relationship(
        Content, back_populates="revisions"
    )
