"""Token staking models: treasury bonds, guild pools, proposal backing."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, String, Float
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TokenStake(Base):
    """A user's staked AGC in one of three pool types."""

    __tablename__ = "token_stakes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    pool_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "treasury" | "guild" | "proposal"
    reference_id: Mapped[UUID | None] = mapped_column(
        nullable=True
    )  # guild_id or proposal_id (null for treasury)
    locked_until: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )  # None = flexible (treasury)
    apy: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Accumulated unclaimed yield
    pending_yield: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Last time compound interest was calculated
    last_compound_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    # Whether the stake has been fully withdrawn
    is_active: Mapped[bool] = mapped_column(default=True)


class TokenYieldRecord(Base):
    """Record of yield claimed from a stake."""

    __tablename__ = "token_yield_records"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    stake_id: Mapped[UUID] = mapped_column(
        ForeignKey("token_stakes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )