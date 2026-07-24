"""Guild leveling: lock members' passed proposals into guild scores."""

from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Guild, GuildMember, GuildMemberProposal, Patch


def calc_guild_level(proposal_score: int) -> int:
    """Map proposal_score to guild level (1-5)."""
    if proposal_score >= 50:
        return 5
    if proposal_score >= 30:
        return 4
    if proposal_score >= 15:
        return 3
    if proposal_score >= 5:
        return 2
    return 1


async def lock_user_proposals(
    session: AsyncSession,
    guild_id: UUID,
    user_id: UUID,
) -> int:
    """Lock all uncounted passed proposals of *user_id* into *guild_id*.

    Called when a user joins a guild.  Returns the number of proposals
    newly locked.
    """
    # Find all passed proposals authored by this user whose id is NOT
    # already in guild_member_proposals (across any guild).
    already = (
        select(GuildMemberProposal.proposal_id)
        .where(GuildMemberProposal.user_id == user_id)
    )

    q = (
        select(Patch.id)
        .where(
            Patch.author_id == user_id,
            Patch.status == "merged",
            Patch.id.not_in(already),
        )
    )
    result = await session.execute(q)
    proposal_ids = [row[0] for row in result.fetchall()]

    if not proposal_ids:
        return 0

    # Insert rows
    for pid in proposal_ids:
        session.add(GuildMemberProposal(
            guild_id=guild_id, user_id=user_id, proposal_id=pid
        ))

    # Bump guild.proposal_score (with row lock to prevent lost updates)
    guild = await session.get(Guild, guild_id, with_for_update=True)
    if guild is not None:
        guild.proposal_score += len(proposal_ids)
        guild.level = calc_guild_level(guild.proposal_score)

    await session.flush()
    return len(proposal_ids)


async def count_proposal_for_guild(
    session: AsyncSession,
    proposal_id: UUID,
    author_id: UUID,
) -> bool:
    """If the proposal author is a member of a guild, lock this newly
    passed proposal into that guild.  Called when a patch status becomes
    'merged'.

    Returns True if the proposal was counted, False otherwise.
    """
    # Check if already counted
    existing = await session.scalar(
        select(GuildMemberProposal).where(
            GuildMemberProposal.proposal_id == proposal_id
        )
    )
    if existing is not None:
        return False

    # Find the author's current approved guild membership
    q = (
        select(GuildMember.guild_id)
        .where(
            GuildMember.user_id == author_id,
            GuildMember.status == "approved",
        )
    )
    result = await session.execute(q)
    guild_id = result.scalars().first()
    if guild_id is None:
        return False

    session.add(GuildMemberProposal(
        guild_id=guild_id, user_id=author_id, proposal_id=proposal_id,
    ))
    guild = await session.get(Guild, guild_id, with_for_update=True)
    if guild is not None:
        guild.proposal_score += 1
        guild.level = calc_guild_level(guild.proposal_score)

    await session.flush()
    return True


async def guild_proposal_contributions(
    session: AsyncSession,
    guild_id: UUID,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """Paginated list of proposal contributions to a guild, with member info."""
    from app.db.models import User

    base = (
        select(GuildMemberProposal, Patch.title, User.username)
        .join(Patch, Patch.id == GuildMemberProposal.proposal_id)
        .join(User, User.id == GuildMemberProposal.user_id)
        .where(GuildMemberProposal.guild_id == guild_id)
        .order_by(GuildMemberProposal.counted_at.desc())
    )

    total = (await session.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar_one()

    rows = (
        (await session.execute(base.offset((page - 1) * page_size).limit(page_size)))
        .all()
    )

    items = [
        {
            "proposal_id": str(row.GuildMemberProposal.proposal_id),
            "title": row.title,
            "username": row.username,
            "counted_at": row.GuildMemberProposal.counted_at.isoformat(),
        }
        for row in rows
    ]
    return items, total
