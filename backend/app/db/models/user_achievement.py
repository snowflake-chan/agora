"""Multi-dimensional achievement / reputation system."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, String, Float, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# ── Achievement definitions ──
# Each achievement has a key, category, and tier thresholds.
# Tiers: 1 = bronze, 2 = silver, 3 = gold, 4 = platinum

ACHIEVEMENT_DEFS: dict[str, dict] = {
    # ── Content Quality ──
    "content_likes": {
        "category": "content_quality",
        "name": "Content Likes",
        "description": "Total likes received across all posts",
        "tiers": {1: 10, 2: 50, 3: 200, 4: 1000},
    },
    "content_replies": {
        "category": "content_quality",
        "name": "Discussion Starter",
        "description": "Total replies received across all posts",
        "tiers": {1: 5, 2: 25, 3: 100, 4: 500},
    },
    "content_engagement_ratio": {
        "category": "content_quality",
        "name": "Engagement Master",
        "description": "Average engagement ratio (likes+replies per post)",
        "tiers": {1: 1.0, 2: 3.0, 3: 8.0, 4: 20.0},
    },
    # ── Proposal Contribution ──
    "proposals_passed": {
        "category": "proposal_contribution",
        "name": "Legislator",
        "description": "Number of proposals that passed",
        "tiers": {1: 1, 2: 3, 3: 8, 4: 20},
    },
    "proposal_votes_cast": {
        "category": "proposal_contribution",
        "name": "Civic Duty",
        "description": "Total votes cast on proposals",
        "tiers": {1: 5, 2: 20, 3: 50, 4: 150},
    },
    "proposal_quality": {
        "category": "proposal_contribution",
        "name": "Policy Maker",
        "description": "Average vote ratio on own proposals (for/total)",
        "tiers": {1: 0.55, 2: 0.65, 3: 0.75, 4: 0.85},
    },
    # ── Guild Governance ──
    "guild_level": {
        "category": "guild_governance",
        "name": "Guild Leader",
        "description": "Highest guild level achieved as president",
        "tiers": {1: 1, 2: 2, 3: 3, 4: 5},
    },
    "guild_members": {
        "category": "guild_governance",
        "name": "Community Builder",
        "description": "Total approved guild members across all guilds led",
        "tiers": {1: 3, 2: 10, 3: 30, 4: 100},
    },
    "guild_proposals": {
        "category": "guild_governance",
        "name": "Guild Contributor",
        "description": "Proposals contributed to guild score",
        "tiers": {1: 1, 2: 5, 3: 15, 4: 50},
    },
    # ── Token Economy ──
    "token_balance": {
        "category": "token_economy",
        "name": "Whale",
        "description": "Highest AGC balance achieved",
        "tiers": {1: 100, 2: 500, 3: 2000, 4: 10000},
    },
    "token_earned": {
        "category": "token_economy",
        "name": "Earner",
        "description": "Total AGC earned",
        "tiers": {1: 50, 2: 300, 3: 1500, 4: 8000},
    },
    "token_staked": {
        "category": "token_economy",
        "name": "Investor",
        "description": "Total AGC staked",
        "tiers": {1: 50, 2: 200, 3: 1000, 4: 5000},
    },
    "token_tipped": {
        "category": "token_economy",
        "name": "Philanthropist",
        "description": "Total AGC tipped to others",
        "tiers": {1: 20, 2: 100, 3: 500, 4: 3000},
    },
    # ── Community Impact ──
    "followers": {
        "category": "community_impact",
        "name": "Influencer",
        "description": "Number of followers",
        "tiers": {1: 5, 2: 20, 3: 100, 4: 500},
    },
    "reports_accurate": {
        "category": "community_impact",
        "name": "Guardian",
        "description": "Accurate reports that led to action",
        "tiers": {1: 1, 2: 5, 3: 15, 4: 50},
    },
    "days_active": {
        "category": "community_impact",
        "name": "Veteran",
        "description": "Days with at least one activity (post/vote/comment)",
        "tiers": {1: 7, 2: 30, 3: 90, 4: 365},
    },
}


class UserAchievement(Base):
    """Record of a user's achieved tier for a specific achievement key."""

    __tablename__ = "user_achievements"

    __table_args__ = (
        UniqueConstraint("user_id", "achievement_key", name="uq_user_achievement_key"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    achievement_key: Mapped[str] = mapped_column(String(50), nullable=False)
    tier: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # 1=bronze, 2=silver, 3=gold, 4=platinum
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    awarded_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )