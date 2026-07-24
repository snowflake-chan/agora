from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class GuildMemberProposal(Base):
    __tablename__ = "guild_member_proposals"
    __table_args__ = (
        UniqueConstraint(
            "proposal_id",
            name="uq_guild_member_proposals_proposal",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    guild_id: Mapped[UUID] = mapped_column(
        ForeignKey("guild.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    proposal_id: Mapped[UUID] = mapped_column(
        ForeignKey("patch.id", ondelete="CASCADE"),
        nullable=False,
    )
    counted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=datetime.now,
        nullable=False,
    )

    # ── Relationships ──
    guild: Mapped["Guild"] = relationship("Guild", back_populates="member_proposals", lazy="joined")
