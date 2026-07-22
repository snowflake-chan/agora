from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PostPoll(Base):
    __tablename__ = "post_poll"
    __table_args__ = (
        UniqueConstraint("post_id", name="uq_post_poll_post"),
        CheckConstraint(
            "char_length(btrim(question)) BETWEEN 5 AND 160",
            name="ck_post_poll_question_length",
        ),
        CheckConstraint(
            "closes_at > created_at",
            name="ck_post_poll_closes_after_creation",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    post_id: Mapped[UUID] = mapped_column(
        ForeignKey("content.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(String(160), nullable=False)
    closes_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, nullable=False
    )

    post: Mapped["Content"] = relationship("Content", back_populates="poll")  # type: ignore[name-defined]
    options: Mapped[list["PostPollOption"]] = relationship(
        "PostPollOption",
        back_populates="poll",
        order_by="PostPollOption.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )


class PostPollOption(Base):
    __tablename__ = "post_poll_option"
    __table_args__ = (
        UniqueConstraint(
            "poll_id", "normalized_digest", name="uq_post_poll_option_digest"
        ),
        UniqueConstraint("poll_id", "id", name="uq_post_poll_option_poll_id_id"),
        UniqueConstraint("poll_id", "position", name="uq_post_poll_option_position"),
        CheckConstraint(
            "char_length(btrim(text)) BETWEEN 1 AND 80",
            name="ck_post_poll_option_text_length",
        ),
        CheckConstraint(
            "position BETWEEN 0 AND 5",
            name="ck_post_poll_option_position",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    poll_id: Mapped[UUID] = mapped_column(
        ForeignKey("post_poll.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(String(80), nullable=False)
    normalized_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    poll: Mapped[PostPoll] = relationship(PostPoll, back_populates="options")


class PostPollVote(Base):
    __tablename__ = "post_poll_vote"
    __table_args__ = (
        UniqueConstraint(
            "poll_id", "user_id", name="uq_post_poll_vote_poll_user"
        ),
        ForeignKeyConstraint(
            ("poll_id", "option_id"),
            ("post_poll_option.poll_id", "post_poll_option.id"),
            name="fk_post_poll_vote_option",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    poll_id: Mapped[UUID] = mapped_column(
        ForeignKey("post_poll.id", ondelete="CASCADE"), nullable=False, index=True
    )
    option_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
