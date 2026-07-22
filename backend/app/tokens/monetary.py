"""Monetary policy engine: inflation/deflation tracking and auto-adjustment."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TokenBalance, TokenSnapshot, TokenTransaction

# ── Target inflation range (monthly, in percent) ──
TARGET_INFLATION_LOWER = 0.5
TARGET_INFLATION_UPPER = 3.0


# ── Snapshot ──


async def record_snapshot(session: AsyncSession) -> dict:
    """Record today's supply snapshot (idempotent: replaces if today exists)."""
    today = date.today()

    # Aggregate from TokenBalance
    row = (
        await session.execute(
            select(
                func.coalesce(func.sum(TokenBalance.balance), 0).label("circulating"),
                func.coalesce(func.sum(TokenBalance.total_earned), 0).label("issued"),
                func.coalesce(func.sum(TokenBalance.total_spent), 0).label("burned"),
                func.count(TokenBalance.user_id).filter(
                    TokenBalance.balance > 0
                ).label("active"),
            )
        )
    ).one()

    circulating = int(row.circulating)
    issued = int(row.issued)
    burned = int(row.burned)
    active = int(row.active)

    # Count transactions in the last 24 hours
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    txn_count = (
        await session.execute(
            select(func.count()).select_from(
                select(TokenTransaction).where(
                    TokenTransaction.created_at >= since
                ).subquery()
            )
        )
    ).scalar_one()

    # Upsert: delete existing row for today then insert
    await session.execute(
        TokenSnapshot.__table__.delete().where(
            TokenSnapshot.snapshot_date == today
        )
    )
    snap = TokenSnapshot(
        snapshot_date=today,
        circulating_supply=circulating,
        total_issued=issued,
        total_burned=burned,
        active_users=active,
        transaction_count_24h=txn_count,
    )
    session.add(snap)
    await session.flush()
    return {
        "snapshot_date": today.isoformat(),
        "circulating_supply": circulating,
        "total_issued": issued,
        "total_burned": burned,
        "active_users": active,
        "transaction_count_24h": txn_count,
    }


# ── Supply history ──


async def get_supply_history(
    session: AsyncSession, days: int = 90
) -> list[dict]:
    """Return time-series snapshot data for charting."""
    since = date.today() - timedelta(days=days)
    rows = (
        (
            await session.execute(
                select(TokenSnapshot)
                .where(TokenSnapshot.snapshot_date >= since)
                .order_by(TokenSnapshot.snapshot_date.asc())
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "date": r.snapshot_date.isoformat(),
            "circulating_supply": r.circulating_supply,
            "total_issued": r.total_issued,
            "total_burned": r.total_burned,
            "active_users": r.active_users,
            "transaction_count_24h": r.transaction_count_24h,
        }
        for r in rows
    ]


# ── Inflation / velocity calculations ──


async def calculate_inflation_rate(
    session: AsyncSession,
) -> dict:
    """Calculate 7-day and 30-day inflation rates from snapshots."""
    today = date.today()

    # Get latest snapshot (or today's live aggregate)
    latest = (
        await session.execute(
            select(TokenSnapshot)
            .order_by(TokenSnapshot.snapshot_date.desc())
            .limit(1)
        )
    ).scalar()

    if latest is None:
        # No snapshots yet — use live data as baseline
        return {"inflation_7d": 0.0, "inflation_30d": 0.0}

    current_supply = latest.circulating_supply

    async def supply_at(days_ago: int) -> int:
        target = today - timedelta(days=days_ago)
        row = (
            await session.execute(
                select(TokenSnapshot)
                .where(TokenSnapshot.snapshot_date <= target)
                .order_by(TokenSnapshot.snapshot_date.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return row.circulating_supply if row else current_supply

    supply_7d_ago = await supply_at(7)
    supply_30d_ago = await supply_at(30)

    def rate(current: int, previous: int) -> float:
        if previous <= 0:
            return 0.0
        return round((current - previous) / previous * 100, 2)

    return {
        "inflation_7d": rate(current_supply, supply_7d_ago),
        "inflation_30d": rate(current_supply, supply_30d_ago),
    }


async def calculate_velocity(session: AsyncSession) -> float:
    """Token velocity = 24h transaction volume / circulating supply."""
    row = (
        await session.execute(
            select(
                func.coalesce(func.sum(TokenBalance.balance), 0).label("supply"),
            )
        )
    ).one()
    supply = int(row.supply)
    if supply <= 0:
        return 0.0

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    vol_row = (
        await session.execute(
            select(
                func.coalesce(
                    func.sum(func.abs(TokenTransaction.amount)), 0
                ).label("volume")
            ).where(TokenTransaction.created_at >= since)
        )
    ).one()
    volume = int(vol_row.volume)
    return round(volume / supply, 4)


# ── Monetary metrics ──


async def get_monetary_metrics(session: AsyncSession) -> dict:
    """Return combined monetary indicators."""
    inflation = await calculate_inflation_rate(session)
    velocity = await calculate_velocity(session)

    # Active users
    active = (
        await session.execute(
            select(func.count()).where(TokenBalance.balance > 0)
        )
    ).scalar_one()

    inflation_30d = inflation.get("inflation_30d", 0.0)
    if inflation_30d < TARGET_INFLATION_LOWER:
        status = "deflating"
    elif inflation_30d > TARGET_INFLATION_UPPER:
        status = "inflating"
    else:
        status = "healthy"

    return {
        "inflation_7d": inflation["inflation_7d"],
        "inflation_30d": inflation_30d,
        "velocity": velocity,
        "active_users": active,
        "status": status,
        "target_lower": TARGET_INFLATION_LOWER,
        "target_upper": TARGET_INFLATION_UPPER,
    }


# ── Auto-adjustment engine ──


async def apply_auto_adjustment(
    session: AsyncSession,
    dry_run: bool = False,
    updated_by: UUID | None = None,
) -> dict:
    """Automatically adjust parameters based on inflation/deflation.

    *dry_run=True* returns suggested changes without applying them.
    """
    from app.tokens.service import get_all_params, set_param

    inflation = await calculate_inflation_rate(session)
    rate_30d = inflation["inflation_30d"]

    params = await get_all_params(session)
    adjustments: dict[str, int] = {}
    reason = ""

    if rate_30d > TARGET_INFLATION_UPPER:
        # ── Cooling: reduce issuance and rewards ──
        factor = min((rate_30d - TARGET_INFLATION_UPPER) / TARGET_INFLATION_UPPER, 1.0)
        for key in ("like_reward", "vote_reward", "daily_login_base", "proposal_pass_reward"):
            adjustments[key] = max(1, int(params[key] * (1 - factor * 0.10)))
        for key in ("boost_price_low", "boost_price_mid", "boost_price_high", "guild_create_fee"):
            adjustments[key] = max(1, int(params[key] * (1 - factor * 0.05)))
        reason = (
            f"Inflation {rate_30d}% above target {TARGET_INFLATION_UPPER}%. "
            f"Reduced parameters by {factor * 0.15:.1%}–{factor * 0.05:.1%}."
        )

    elif rate_30d < TARGET_INFLATION_LOWER:
        # ── Stimulus: increase issuance and rewards ──
        factor = min((TARGET_INFLATION_LOWER - rate_30d) / max(TARGET_INFLATION_LOWER, 0.1), 1.0)
        for key in ("like_reward", "vote_reward", "daily_login_base", "proposal_pass_reward"):
            adjustments[key] = max(1, int(params[key] * (1 + factor * 0.10)))
        for key in ("boost_price_low", "boost_price_mid", "boost_price_high", "guild_create_fee"):
            adjustments[key] = max(1, int(params[key] * (1 + factor * 0.05)))
        reason = (
            f"Inflation {rate_30d}% below target {TARGET_INFLATION_LOWER}%. "
            f"Increased parameters by {factor * 0.20:.1%}–{factor * 0.05:.1%}."
        )

    else:
        # ── In target range: no adjustment needed ──
        return {
            "adjusted": False,
            "reason": f"Inflation {rate_30d}% is within target range "
                       f"({TARGET_INFLATION_LOWER}%–{TARGET_INFLATION_UPPER}%). No changes.",
            "adjustments": {},
        }

    if dry_run:
        return {
            "adjusted": False,
            "reason": reason,
            "adjustments": adjustments,
            "dry_run": True,
        }

    # Apply adjustments
    for key, value in adjustments.items():
        await set_param(session, key, value, updated_by=updated_by)
    await session.flush()

    return {
        "adjusted": True,
        "reason": reason,
        "adjustments": adjustments,
        "dry_run": False,
    }
