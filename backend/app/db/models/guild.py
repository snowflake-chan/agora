from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Guild(Base):
    __tablename__ = "guild"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    logo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    president_id: Mapped[UUID] = mapped_column(ForeignKey("user.id", ondelete="RESTRICT"))

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now, nullable=False
    )

    # ── Relationships ──
    president: Mapped["User"] = relationship("User", lazy="joined")  # type: ignore[name-defined]
    members: Mapped[list["GuildMember"]] = relationship("GuildMember", back_populates="guild", lazy="selectin", cascade="all, delete-orphan")


class GuildMember(Base):
    __tablename__ = "guild_member"
    __table_args__ = (
        UniqueConstraint("guild_id", "user_id", name="uq_guild_user"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    guild_id: Mapped[UUID] = mapped_column(ForeignKey("guild.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    # "president" | "vice_president" | "member"
    role: Mapped[str] = mapped_column(String(20), default="member")
    # "pending" | "approved" | "rejected"
    status: Mapped[str] = mapped_column(String(20), default="approved")
    joined_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.now, nullable=False
    )

    # ── Relationships ──
    guild: Mapped["Guild"] = relationship("Guild", back_populates="members", lazy="joined")
    user: Mapped["User"] = relationship("User", lazy="joined")  # type: ignore[name-defined]
