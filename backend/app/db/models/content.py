from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Content(Base):
    __tablename__ = "content"

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
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)))

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
    author: Mapped["User"] = relationship("User", lazy="joined")  # type: ignore[name-defined]
