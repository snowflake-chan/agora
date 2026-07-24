"""Staking service: treasury bonds, guild pools, proposal backing.

Realistic simulation with compound interest, dynamic APY, and risk tiers.
"""

import math
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TokenStake, TokenYieldRecord, Guild, Patch
from app.tokens.service import get_balance, spend, earn, get_param
from app.tokens.monetary import calculate_inflation_rate

# ── Pool configuration ──

POOL_CONFIG: dict[str, dict] = {
    "treasury": {
        "name": "Treasury Bond",
        "description": "Low risk, flexible withdrawal. Yield comes from system fees.",
        "base_apy": 5.0,       # 5% base annual yield
        "lock_days": 0,         # No lock (flexible)
        "risk_level": "low",
        "min_stake": 10,
    },
    "guild": {
        "name": "Guild Pool",
        "description": "Stake in a guild. Higher yield if the guild performs well.",
        "base_apy": 8.0,        # 8% base
        "lock_days": 30,
        "risk_level": "medium",
        "min_stake": 50,
    },
    "proposal": {
        "name": "Proposal Backing",
        "description": "Stake on a proposal. Earn yield only if it passes.",
        "base_apy": 15.0,       # 15% base (high risk)
        "lock_days": 0,         # Locked until proposal resolution
        "risk_level": "high",
        "min_stake": 20,
    },
}

# ── APY calculation ──


async def calculate_apy(
    session: AsyncSession,
    pool_type: str,
    reference_id: UUID | None = None,
) -> float:
    """Calculate the current APY for a given pool type.

    Treasury: base_apy adjusted by inflation (higher inflation = lower APY to cool down)
    Guild: base_apy * guild_performance_multiplier
    Proposal: base_apy (fixed, resolved at settlement)
    """
    config = POOL_CONFIG.get(pool_type)
    if config is None:
        raise ValueError(f"Unknown pool type: {pool_type}")
    base = config["base_apy"]

    inflation = await calculate_inflation_rate(session)
    rate_30d = inflation["inflation_30d"]

    if pool_type == "treasury":
        # Inflation adjustment: if inflating, reduce APY; if deflating, increase
        if rate_30d > 3.0:
            factor = max(0.5, 1.0 - (rate_30d - 3.0) / 10.0)
        elif rate_30d < 0.5:
            factor = min(2.0, 1.0 + (0.5 - rate_30d) / 2.0)
        else:
            factor = 1.0
        return round(base * factor, 2)

    elif pool_type == "guild":
        if reference_id is None:
            return base
        guild = await session.get(Guild, reference_id)
        if guild is None:
            return base
        # Performance multiplier based on guild level (1-5) and proposal score
        level_mult = 1.0 + (guild.level - 1) * 0.15  # 1.0 to 1.6
        score_mult = 1.0 + min(guild.proposal_score / 50.0, 0.5)  # up to 1.5x
        return round(base * level_mult * score_mult, 2)

    elif pool_type == "proposal":
        return base

    return base


# ── Compound interest ──


def compound_interest(
    principal: int,
    apy: float,
    last_compound_at: datetime,
    now: datetime | None = None,
) -> tuple[int, int]:
    """Calculate compound interest earned since last_compound_at.

    Uses continuous compounding: A = P * e^(r * t)
    where t is fraction of a year.

    Returns (new_principal, yield_earned).
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if last_compound_at.tzinfo is None:
        last_compound_at = last_compound_at.replace(tzinfo=timezone.utc)

    delta = now - last_compound_at
    years = delta.total_seconds() / (365.25 * 24 * 3600)
    if years <= 0 or principal <= 0:
        return principal, 0

    rate = apy / 100.0
    new_principal = int(principal * math.exp(rate * years))
    yield_earned = max(0, new_principal - principal)
    return new_principal, yield_earned


# ── Stake operations ──


async def stake(
    session: AsyncSession,
    user_id: UUID,
    amount: int,
    pool_type: str,
    reference_id: UUID | None = None,
) -> TokenStake:
    """Stake AGC into a pool. Deducts from balance immediately."""
    config = POOL_CONFIG.get(pool_type)
    if config is None:
        raise ValueError(f"Unknown pool type: {pool_type}")

    if amount < config["min_stake"]:
        raise ValueError(
            f"Minimum stake for {pool_type} is {config['min_stake']} AGC"
        )

    # Deduct from balance
    await spend(session, user_id, amount, "stake")

    # Calculate lock period
    locked_until = None
    if pool_type == "guild":
        locked_until = datetime.now(timezone.utc) + timedelta(days=config["lock_days"])
    elif pool_type == "proposal":
        # Locked until proposal resolution — set far future, will be updated
        if reference_id is None:
            raise ValueError("reference_id (proposal_id) required for proposal staking")
        locked_until = datetime.now(timezone.utc) + timedelta(days=90)

    apy = await calculate_apy(session, pool_type, reference_id)

    stake_row = TokenStake(
        user_id=user_id,
        amount=amount,
        pool_type=pool_type,
        reference_id=reference_id,
        locked_until=locked_until,
        apy=apy,
        last_compound_at=datetime.now(timezone.utc),
    )
    session.add(stake_row)
    await session.flush()
    return stake_row


async def unstake(
    session: AsyncSession,
    stake_id: UUID,
    user_id: UUID,
) -> dict:
    """Withdraw a stake and all pending yield. Deducts early withdrawal penalty if locked."""
    stake_row = await session.get(TokenStake, stake_id, with_for_update=True)
    if stake_row is None:
        raise ValueError("Stake not found")
    if stake_row.user_id != user_id:
        raise ValueError("Not your stake")
    if not stake_row.is_active:
        raise ValueError("Stake already withdrawn")

    now = datetime.now(timezone.utc)

    # Check lock
    penalty = 0
    if stake_row.locked_until and now < stake_row.locked_until:
        # Early withdrawal: 20% penalty on principal
        penalty = int(stake_row.amount * 0.20)
        # Burn the penalty (spend without earning)
        # Actually we just don't return it — it goes to the treasury implicitly

    # Compound interest first
    _, yield_earned = compound_interest(
        stake_row.amount, stake_row.apy, stake_row.last_compound_at, now
    )
    total_yield = stake_row.pending_yield + yield_earned

    principal_return = max(0, stake_row.amount - penalty)
    total_return = principal_return + total_yield

    # Mark inactive
    stake_row.is_active = False
    stake_row.pending_yield = 0

    # Credit user
    if total_return > 0:
        await earn(session, user_id, total_return, "stake_unstake", bypass_cap=True)

    # Record yield
    if total_yield > 0:
        session.add(TokenYieldRecord(
            stake_id=stake_id,
            user_id=user_id,
            amount=total_yield,
        ))

    await session.flush()

    return {
        "principal_returned": principal_return,
        "yield_earned": total_yield,
        "penalty": penalty,
        "total_returned": total_return,
    }


async def claim_yield(
    session: AsyncSession,
    stake_id: UUID,
    user_id: UUID,
) -> dict:
    """Claim pending yield without unstaking."""
    stake_row = await session.get(TokenStake, stake_id, with_for_update=True)
    if stake_row is None:
        raise ValueError("Stake not found")
    if stake_row.user_id != user_id:
        raise ValueError("Not your stake")
    if not stake_row.is_active:
        raise ValueError("Stake is inactive")

    now = datetime.now(timezone.utc)

    # Compound
    _, yield_earned = compound_interest(
        stake_row.amount, stake_row.apy, stake_row.last_compound_at, now
    )
    total_yield = stake_row.pending_yield + yield_earned

    if total_yield <= 0:
        return {"claimed": 0}

    stake_row.pending_yield = 0
    stake_row.last_compound_at = now

    await earn(session, user_id, total_yield, "stake_yield", bypass_cap=True)

    session.add(TokenYieldRecord(
        stake_id=stake_id,
        user_id=user_id,
        amount=total_yield,
    ))
    await session.flush()

    return {"claimed": total_yield}


async def compound_all_stakes(
    session: AsyncSession,
    user_id: UUID | None = None,
) -> int:
    """Run compound interest calculation for all active stakes (or one user's).
    Returns total yield accrued across all stakes.
    """
    q = select(TokenStake).where(TokenStake.is_active == True)
    if user_id is not None:
        q = q.where(TokenStake.user_id == user_id)

    stakes = (await session.execute(q)).scalars().all()
    total_yield = 0
    now = datetime.now(timezone.utc)

    for s in stakes:
        new_principal, earned = compound_interest(s.amount, s.apy, s.last_compound_at, now)
        if earned > 0:
            s.amount = new_principal
            s.pending_yield += earned
            s.last_compound_at = now
            total_yield += earned

    if total_yield > 0:
        await session.flush()
    return total_yield


async def list_user_stakes(
    session: AsyncSession,
    user_id: UUID,
    include_inactive: bool = False,
) -> list[dict]:
    """List all stakes for a user with current APY and yield info."""
    q = select(TokenStake).where(TokenStake.user_id == user_id)
    if not include_inactive:
        q = q.where(TokenStake.is_active == True)
    q = q.order_by(TokenStake.created_at.desc())

    stakes = (await session.execute(q)).scalars().all()
    now = datetime.now(timezone.utc)

    result = []
    for s in stakes:
        _, pending = compound_interest(s.amount, s.apy, s.last_compound_at, now)
        total_pending = s.pending_yield + pending
        result.append({
            "id": str(s.id),
            "amount": s.amount,
            "pool_type": s.pool_type,
            "reference_id": str(s.reference_id) if s.reference_id else None,
            "locked_until": s.locked_until.isoformat() if s.locked_until else None,
            "apy": s.apy,
            "pending_yield": total_pending,
            "is_active": s.is_active,
            "created_at": s.created_at.isoformat(),
        })
    return result


async def get_user_staking_stats(
    session: AsyncSession,
    user_id: UUID,
) -> dict:
    """Get aggregate staking stats for a user."""
    q = (
        select(
            func.coalesce(func.sum(TokenStake.amount), 0).label("total_staked"),
            func.coalesce(func.sum(TokenStake.pending_yield), 0).label("total_pending_yield"),
            func.count(TokenStake.id).label("active_stakes"),
        )
        .where(TokenStake.user_id == user_id, TokenStake.is_active == True)
    )
    row = (await session.execute(q)).one()

    # Calculate pending yield from compounding
    stakes = (
        await session.execute(
            select(TokenStake).where(
                TokenStake.user_id == user_id, TokenStake.is_active == True
            )
        )
    ).scalars().all()

    now = datetime.now(timezone.utc)
    compound_yield = 0
    for s in stakes:
        _, earned = compound_interest(s.amount, s.apy, s.last_compound_at, now)
        compound_yield += earned

    return {
        "total_staked": int(row.total_staked),
        "total_pending_yield": int(row.total_pending_yield) + compound_yield,
        "active_stakes": int(row.active_stakes),
    }


async def settle_proposal_stakes(
    session: AsyncSession,
    proposal_id: UUID,
    passed: bool,
) -> int:
    """Settle all stakes on a proposal. If passed, pay yield; if failed, lose principal.

    Returns the number of stakes settled.
    """
    q = (
        select(TokenStake)
        .where(
            TokenStake.pool_type == "proposal",
            TokenStake.reference_id == proposal_id,
            TokenStake.is_active == True,
        )
        .with_for_update()
    )
    stakes = (await session.execute(q)).scalars().all()

    for s in stakes:
        now = datetime.now(timezone.utc)
        if passed:
            # Compound and credit
            _, yield_earned = compound_interest(
                s.amount, s.apy, s.last_compound_at, now
            )
            total_yield = s.pending_yield + yield_earned
            total_return = s.amount + total_yield
            await earn(session, s.user_id, total_return, "proposal_backing_win", bypass_cap=True)
            if total_yield > 0:
                session.add(TokenYieldRecord(
                    stake_id=s.id, user_id=s.user_id, amount=total_yield,
                ))
        else:
            # Principal lost — no return
            pass

        s.is_active = False
        s.pending_yield = 0

    await session.flush()
    return len(stakes)