"""Achievement calculation engine.

Computes achievement scores across 5 dimensions:
- content_quality: likes, replies, engagement ratio
- proposal_contribution: passed proposals, votes cast, quality ratio
- guild_governance: guild level, members, proposals
- token_economy: balance, earned, staked, tipped
- community_impact: followers, accurate reports, days active
"""

import math
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    UserAchievement,
    PostLike,
    Content,
    Patch,
    Vote,
    Guild,
    GuildMember,
    GuildMemberProposal,
    TokenBalance,
    TokenTransaction,
    TokenStake,
    Follow,
    Report,
)
from app.db.models.user_achievement import ACHIEVEMENT_DEFS


def _calc_tier(score: float, tiers: dict[int, float]) -> int:
    """Determine which tier (1-4) the score reaches."""
    result = 0
    for tier, threshold in sorted(tiers.items()):
        if score >= threshold:
            result = tier
    return result


async def calculate_scores(
    session: AsyncSession,
    user_id: UUID,
) -> dict[str, dict]:
    """Calculate all achievement scores for a user.

    Returns a dict of {achievement_key: {score, tier, category, name}}.
    """
    results: dict[str, dict] = {}

    # ── Content Quality ──

    # Total likes received
    likes_count = (
        await session.execute(
            select(func.count())
            .select_from(PostLike)
            .join(Content, Content.id == PostLike.post_id)
            .where(Content.author_id == user_id)
        )
    ).scalar_one()

    # Total replies received
    replies_count = (
        await session.execute(
            select(func.count())
            .select_from(Content)
            .where(
                Content.author_id == user_id,
                Content.replying_id.isnot(None),
            )
        )
    ).scalar_one()

    # Engagement ratio
    post_count = (
        await session.execute(
            select(func.count())
            .select_from(Content)
            .where(Content.author_id == user_id)
        )
    ).scalar_one()
    engagement_ratio = (likes_count + replies_count) / max(1, post_count)

    results["content_likes"] = {
        "score": likes_count,
        "tier": _calc_tier(likes_count, ACHIEVEMENT_DEFS["content_likes"]["tiers"]),
        "category": "content_quality",
        "name": ACHIEVEMENT_DEFS["content_likes"]["name"],
    }
    results["content_replies"] = {
        "score": replies_count,
        "tier": _calc_tier(replies_count, ACHIEVEMENT_DEFS["content_replies"]["tiers"]),
        "category": "content_quality",
        "name": ACHIEVEMENT_DEFS["content_replies"]["name"],
    }
    results["content_engagement_ratio"] = {
        "score": round(engagement_ratio, 2),
        "tier": _calc_tier(engagement_ratio, ACHIEVEMENT_DEFS["content_engagement_ratio"]["tiers"]),
        "category": "content_quality",
        "name": ACHIEVEMENT_DEFS["content_engagement_ratio"]["name"],
    }

    # ── Proposal Contribution ──

    proposals_passed = (
        await session.execute(
            select(func.count())
            .select_from(Patch)
            .where(Patch.author_id == user_id, Patch.status == "merged")
        )
    ).scalar_one()

    votes_cast = (
        await session.execute(
            select(func.count())
            .select_from(Vote)
            .where(Vote.voter_id == user_id)
        )
    ).scalar_one()

    # Proposal quality: average for/total ratio
    own_patches = (
        await session.execute(
            select(Patch.id).where(Patch.author_id == user_id)
        )
    ).scalars().all()
    proposal_quality = 0.0
    if own_patches:
        total_votes_on_own = (
            await session.execute(
                select(func.count())
                .select_from(Vote)
                .where(Vote.patch_id.in_([p for p in own_patches]))
            )
        ).scalar_one()
        for_votes = (
            await session.execute(
                select(func.count())
                .select_from(Vote)
                .where(
                    Vote.patch_id.in_([p for p in own_patches]),
                    Vote.choice == "for",
                )
            )
        ).scalar_one()
        if total_votes_on_own > 0:
            proposal_quality = for_votes / total_votes_on_own

    results["proposals_passed"] = {
        "score": proposals_passed,
        "tier": _calc_tier(proposals_passed, ACHIEVEMENT_DEFS["proposals_passed"]["tiers"]),
        "category": "proposal_contribution",
        "name": ACHIEVEMENT_DEFS["proposals_passed"]["name"],
    }
    results["proposal_votes_cast"] = {
        "score": votes_cast,
        "tier": _calc_tier(votes_cast, ACHIEVEMENT_DEFS["proposal_votes_cast"]["tiers"]),
        "category": "proposal_contribution",
        "name": ACHIEVEMENT_DEFS["proposal_votes_cast"]["name"],
    }
    results["proposal_quality"] = {
        "score": round(proposal_quality, 4),
        "tier": _calc_tier(proposal_quality, ACHIEVEMENT_DEFS["proposal_quality"]["tiers"]),
        "category": "proposal_contribution",
        "name": ACHIEVEMENT_DEFS["proposal_quality"]["name"],
    }

    # ── Guild Governance ──

    # Find guilds where user is president
    president_guilds = (
        await session.execute(
            select(Guild).where(Guild.president_id == user_id)
        )
    ).scalars().all()

    max_guild_level = max((g.level for g in president_guilds), default=0)
    total_guild_members = 0
    if president_guilds:
        total_guild_members = (
            await session.execute(
                select(func.count())
                .select_from(GuildMember)
                .where(
                    GuildMember.guild_id.in_([g.id for g in president_guilds]),
                    GuildMember.status == "approved",
                )
            )
        ).scalar_one()

    # Guild proposals contributed (as member)
    guild_proposals = (
        await session.execute(
            select(func.count())
            .select_from(GuildMemberProposal)
            .where(GuildMemberProposal.user_id == user_id)
        )
    ).scalar_one()

    results["guild_level"] = {
        "score": max_guild_level,
        "tier": _calc_tier(max_guild_level, ACHIEVEMENT_DEFS["guild_level"]["tiers"]),
        "category": "guild_governance",
        "name": ACHIEVEMENT_DEFS["guild_level"]["name"],
    }
    results["guild_members"] = {
        "score": total_guild_members,
        "tier": _calc_tier(total_guild_members, ACHIEVEMENT_DEFS["guild_members"]["tiers"]),
        "category": "guild_governance",
        "name": ACHIEVEMENT_DEFS["guild_members"]["name"],
    }
    results["guild_proposals"] = {
        "score": guild_proposals,
        "tier": _calc_tier(guild_proposals, ACHIEVEMENT_DEFS["guild_proposals"]["tiers"]),
        "category": "guild_governance",
        "name": ACHIEVEMENT_DEFS["guild_proposals"]["name"],
    }

    # ── Token Economy ──

    balance_row = await session.get(TokenBalance, user_id)
    balance = balance_row.balance if balance_row else 0
    total_earned = balance_row.total_earned if balance_row else 0

    # Total staked
    total_staked = (
        await session.execute(
            select(func.coalesce(func.sum(TokenStake.amount), 0))
            .where(TokenStake.user_id == user_id, TokenStake.is_active == True)
        )
    ).scalar_one()

    # Total tipped
    total_tipped = (
        await session.execute(
            select(func.coalesce(func.sum(func.abs(TokenTransaction.amount)), 0))
            .where(
                TokenTransaction.user_id == user_id,
                TokenTransaction.source == "tip_send",
            )
        )
    ).scalar_one()

    results["token_balance"] = {
        "score": balance,
        "tier": _calc_tier(balance, ACHIEVEMENT_DEFS["token_balance"]["tiers"]),
        "category": "token_economy",
        "name": ACHIEVEMENT_DEFS["token_balance"]["name"],
    }
    results["token_earned"] = {
        "score": total_earned,
        "tier": _calc_tier(total_earned, ACHIEVEMENT_DEFS["token_earned"]["tiers"]),
        "category": "token_economy",
        "name": ACHIEVEMENT_DEFS["token_earned"]["name"],
    }
    results["token_staked"] = {
        "score": total_staked,
        "tier": _calc_tier(total_staked, ACHIEVEMENT_DEFS["token_staked"]["tiers"]),
        "category": "token_economy",
        "name": ACHIEVEMENT_DEFS["token_staked"]["name"],
    }
    results["token_tipped"] = {
        "score": total_tipped,
        "tier": _calc_tier(total_tipped, ACHIEVEMENT_DEFS["token_tipped"]["tiers"]),
        "category": "token_economy",
        "name": ACHIEVEMENT_DEFS["token_tipped"]["name"],
    }

    # ── Community Impact ──

    followers_count = (
        await session.execute(
            select(func.count())
            .select_from(Follow)
            .where(Follow.following_id == user_id)
        )
    ).scalar_one()

    accurate_reports = (
        await session.execute(
            select(func.count())
            .select_from(Report)
            .where(
                Report.reporter_id == user_id,
                Report.status == "resolved",
            )
        )
    ).scalar_one()

    # Days active: count distinct days with any activity
    days_active = 0
    # Count from content
    content_days = (
        await session.execute(
            select(func.count(func.distinct(func.date(Content.created_at))))
            .where(Content.author_id == user_id)
        )
    ).scalar_one()
    # Count from votes
    vote_days = (
        await session.execute(
            select(func.count(func.distinct(func.date(Vote.created_at))))
            .where(Vote.voter_id == user_id)
        )
    ).scalar_one()
    days_active = max(content_days, vote_days)

    results["followers"] = {
        "score": followers_count,
        "tier": _calc_tier(followers_count, ACHIEVEMENT_DEFS["followers"]["tiers"]),
        "category": "community_impact",
        "name": ACHIEVEMENT_DEFS["followers"]["name"],
    }
    results["reports_accurate"] = {
        "score": accurate_reports,
        "tier": _calc_tier(accurate_reports, ACHIEVEMENT_DEFS["reports_accurate"]["tiers"]),
        "category": "community_impact",
        "name": ACHIEVEMENT_DEFS["reports_accurate"]["name"],
    }
    results["days_active"] = {
        "score": days_active,
        "tier": _calc_tier(days_active, ACHIEVEMENT_DEFS["days_active"]["tiers"]),
        "category": "community_impact",
        "name": ACHIEVEMENT_DEFS["days_active"]["name"],
    }

    return results


async def sync_achievements(
    session: AsyncSession,
    user_id: UUID,
) -> list[dict]:
    """Calculate scores and upsert achievement records. Returns newly earned achievements."""
    scores = await calculate_scores(session, user_id)
    newly_earned = []

    for key, info in scores.items():
        tier = info["tier"]
        if tier == 0:
            continue

        existing = await session.scalar(
            select(UserAchievement).where(
                UserAchievement.user_id == user_id,
                UserAchievement.achievement_key == key,
            )
        )
        if existing is None:
            # New achievement
            ach = UserAchievement(
                user_id=user_id,
                achievement_key=key,
                tier=tier,
                score=info["score"],
            )
            session.add(ach)
            newly_earned.append({
                "key": key,
                "name": info["name"],
                "category": info["category"],
                "tier": tier,
                "score": info["score"],
                "previous_tier": 0,
            })
        elif existing.tier < tier:
            # Leveled up
            previous_tier = existing.tier
            existing.tier = tier
            existing.score = info["score"]
            existing.awarded_at = datetime.now(timezone.utc)
            newly_earned.append({
                "key": key,
                "name": info["name"],
                "category": info["category"],
                "tier": tier,
                "score": info["score"],
                "previous_tier": previous_tier,
            })
        elif existing.score != info["score"]:
            # Just update score
            existing.score = info["score"]

    await session.flush()
    return newly_earned


async def get_user_achievements(
    session: AsyncSession,
    user_id: UUID,
) -> dict:
    """Get all achievements for a user, organized by category."""
    scores = await calculate_scores(session, user_id)
    records = (
        await session.execute(
            select(UserAchievement).where(UserAchievement.user_id == user_id)
        )
    ).scalars().all()
    record_map = {r.achievement_key: r for r in records}

    categories: dict[str, list[dict]] = {}
    for key, info in scores.items():
        cat = info["category"]
        if cat not in categories:
            categories[cat] = []

        recorded = record_map.get(key)
        # Use the highest tier between current score and recorded
        current_tier = info["tier"]
        recorded_tier = recorded.tier if recorded else 0
        best_tier = max(current_tier, recorded_tier)

        categories[cat].append({
            "key": key,
            "name": info["name"],
            "score": info["score"],
            "tier": best_tier,
            "tier_label": ["", "bronze", "silver", "gold", "platinum"][best_tier],
            "max_tier": 4,
            "thresholds": ACHIEVEMENT_DEFS[key]["tiers"],
        })

    # Category labels
    category_labels = {
        "content_quality": "Content Quality",
        "proposal_contribution": "Proposal Contribution",
        "guild_governance": "Guild Governance",
        "token_economy": "Token Economy",
        "community_impact": "Community Impact",
    }

    return {
        "categories": [
            {"key": cat, "label": category_labels.get(cat, cat), "achievements": items}
            for cat, items in categories.items()
        ]
    }