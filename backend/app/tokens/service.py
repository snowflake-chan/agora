"""AGC token economy service: balance, transactions, earning, spending, params."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TokenBalance, TokenTransaction, TokenParam, TokenParamHistory

# ── Default parameter values ──
DEFAULT_PARAMS: dict[str, int] = {
    "like_reward": 2,
    "vote_reward": 2,
    "proposal_pass_reward": 100,
    "daily_login_base": 3,
    "proposal_deposit": 50,
    "boost_price_low": 10,
    "boost_price_mid": 30,
    "boost_price_high": 50,
    "guild_create_fee": 200,
    "daily_user_cap": 200,
}


# ── Param helpers ──

async def get_param(session: AsyncSession, key: str) -> int:
    """Read a token economy parameter, falling back to the default."""
    row = await session.get(TokenParam, key)
    if row is not None:
        return row.value
    return DEFAULT_PARAMS.get(key, 0)


async def get_all_params(session: AsyncSession) -> dict[str, int]:
    """Return all parameters as a dict, filling missing with defaults."""
    result = dict(DEFAULT_PARAMS)
    rows = (await session.execute(select(TokenParam))).scalars().all()
    for row in rows:
        result[row.key] = row.value
    return result


async def set_param(
    session: AsyncSession,
    key: str,
    value: int,
    updated_by: UUID | None = None,
) -> None:
    """Update a parameter value and record history."""
    old = await get_param(session, key)
    now = datetime.now(timezone.utc)

    param = await session.get(TokenParam, key)
    if param is None:
        param = TokenParam(key=key, value=value, updated_by=updated_by, updated_at=now)
        session.add(param)
    else:
        param.value = value
        param.updated_by = updated_by
        param.updated_at = now

    history = TokenParamHistory(
        key=key,
        old_value=old,
        new_value=value,
        changed_by=updated_by,
        changed_at=now,
    )
    session.add(history)


# ── Balance helpers ──

async def get_balance(session: AsyncSession, user_id: UUID) -> TokenBalance:
    """Return (or create) a token balance row for *user_id*.

    Uses SELECT ... FOR UPDATE to lock the row, preventing lost updates
    from concurrent earn/spend/tip operations.
    """
    row = await session.get(TokenBalance, user_id, with_for_update=True)
    if row is None:
        row = TokenBalance(user_id=user_id)
        session.add(row)
        await session.flush()
        # Re-fetch with lock after insert
        row = await session.get(TokenBalance, user_id, with_for_update=True)
    return row


# ── Cap & throttling helpers ──

# Sources that bypass the per-user daily cap (e.g. rewards explicitly
# excluded by the design, or transfers between users).
_CAP_EXCLUDED_SOURCES: set[str] = {
    "daily_login",
    "proposal_pass",
    "proposal_deposit_refund",
    "receive",
}


async def _today_earned(session: AsyncSession, user_id: UUID) -> int:
    """Sum of capped positive earnings for *user_id* today (UTC)."""
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    result = await session.execute(
        select(func.coalesce(func.sum(TokenTransaction.amount), 0)).where(
            TokenTransaction.user_id == user_id,
            TokenTransaction.amount > 0,
            TokenTransaction.type == "earn",
            TokenTransaction.source.not_in(_CAP_EXCLUDED_SOURCES),
            TokenTransaction.created_at >= today,
        )
    )
    return int(result.scalar_one())


async def _is_new_user(session: AsyncSession, user_id: UUID) -> bool:
    """True if the user registered within the last 7 days."""
    from app.db.models import User
    row = await session.get(User, user_id)
    if row is None:
        return False
    if row.created_at.tzinfo is None:
        created_at = row.created_at.replace(tzinfo=timezone.utc)
    else:
        created_at = row.created_at
    age = datetime.now(timezone.utc) - created_at
    return age.days < 7


# ── Earn ──

async def earn(
    session: AsyncSession,
    user_id: UUID,
    amount: int,
    source: str,
    reference_id: UUID | None = None,
    bypass_cap: bool = False,
    bypass_new_user_rate: bool = False,
) -> int:
    """Credit *amount* AGC to *user_id*.  Returns the new balance.

    Enforces the daily per-user cap unless *bypass_cap* is True.
    Applies 50 % rate for users registered within the last 7 days unless
    *bypass_new_user_rate* is True (used for one-time welcome bonuses).
    """
    if amount <= 0:
        return (await get_balance(session, user_id)).balance

    if not bypass_new_user_rate and await _is_new_user(session, user_id):
        amount = max(1, amount // 2)

    if not bypass_cap:
        cap = await get_param(session, "daily_user_cap")
        already = await _today_earned(session, user_id)
        room = max(0, cap - already)
        amount = min(amount, room)

    if amount <= 0:
        return (await get_balance(session, user_id)).balance

    row = await get_balance(session, user_id)
    row.balance += amount
    row.total_earned += amount

    txn = TokenTransaction(
        user_id=user_id,
        amount=amount,
        type="earn",
        source=source,
        reference_id=reference_id,
        balance_after=row.balance,
    )
    session.add(txn)
    await session.flush()
    return row.balance


# ── Spend ──

async def spend(
    session: AsyncSession,
    user_id: UUID,
    amount: int,
    source: str,
    reference_id: UUID | None = None,
) -> int:
    """Debit *amount* AGC from *user_id*.  Raises ValueError if insufficient."""
    if amount <= 0:
        return (await get_balance(session, user_id)).balance

    row = await get_balance(session, user_id)
    if row.balance < amount:
        raise ValueError(f"Insufficient balance: have {row.balance}, need {amount}")

    row.balance -= amount
    row.total_spent += amount

    txn = TokenTransaction(
        user_id=user_id,
        amount=-amount,
        type="spend",
        source=source,
        reference_id=reference_id,
        balance_after=row.balance,
    )
    session.add(txn)
    await session.flush()
    return row.balance


# ── Tip ──

async def tip(
    session: AsyncSession,
    from_user_id: UUID,
    to_user_id: UUID,
    amount: int,
    reference_id: UUID | None = None,
) -> int:
    """Transfer *amount* AGC from one user to another."""
    if from_user_id == to_user_id:
        raise ValueError("Cannot tip yourself")
    if amount <= 0:
        raise ValueError("Tip amount must be positive")

    from_row = await get_balance(session, from_user_id)
    if from_row.balance < amount:
        raise ValueError(f"Insufficient balance: have {from_row.balance}, need {amount}")

    from_row.balance -= amount
    from_row.total_spent += amount

    to_row = await get_balance(session, to_user_id)
    to_row.balance += amount
    to_row.total_earned += amount

    now = datetime.now(timezone.utc)
    session.add(TokenTransaction(
        user_id=from_user_id, amount=-amount, type="spend",
        source="tip_send", reference_id=reference_id,
        balance_after=from_row.balance, created_at=now,
    ))
    session.add(TokenTransaction(
        user_id=to_user_id, amount=amount, type="receive",
        source="tip_receive", reference_id=reference_id,
        balance_after=to_row.balance, created_at=now,
    ))
    await session.flush()
    return from_row.balance


# ── Supply stats ──

async def supply_stats(session: AsyncSession) -> dict:
    """Return a dict of supply monitoring metrics."""
    row = (await session.execute(
        select(
            func.coalesce(func.sum(TokenBalance.balance), 0).label("circulating"),
            func.coalesce(func.sum(TokenBalance.total_earned), 0).label("total_issued"),
            func.coalesce(func.sum(TokenBalance.total_spent), 0).label("total_burned"),
        )
    )).one()

    return {
        "circulating_supply": int(row.circulating),
        "total_issued": int(row.total_issued),
        "total_burned": int(row.total_burned),
    }


# ── Daily login ──

async def daily_login(session: AsyncSession, user_id: UUID) -> dict:
    """Claim daily login reward.

    Rewards increase by 1 AGC for each consecutive day, resetting after 7 days.
    Daily login rewards bypass the per-user daily cap.
    """
    base = await get_param(session, "daily_login_base")

    # Gather previous daily-login dates (UTC)
    txns = (
        await session.execute(
            select(TokenTransaction)
            .where(
                TokenTransaction.user_id == user_id,
                TokenTransaction.source == "daily_login",
            )
            .order_by(TokenTransaction.created_at.desc())
        )
    ).scalars().all()

    dates = sorted({t.created_at.date() for t in txns}, reverse=True)
    today = datetime.now(timezone.utc).date()

    if dates and dates[0] == today:
        # Already claimed today — return the reward from the latest transaction.
        latest = next(t for t in txns if t.created_at.date() == today)
        streak = min(len(dates), 7)  # best-effort streak for today
        return {
            "reward": latest.amount,
            "streak": streak,
            "already_claimed": True,
            "balance": (await get_balance(session, user_id)).balance,
        }

    # Count consecutive days ending yesterday
    streak = 0
    check_day = today - timedelta(days=1)
    date_set = set(dates)
    while check_day in date_set and streak < 7:
        streak += 1
        check_day -= timedelta(days=1)

    streak += 1  # today is the next day
    if streak > 7:
        streak = 1

    reward = base + (streak - 1)
    balance = await earn(
        session, user_id, reward, "daily_login", bypass_cap=True
    )
    return {
        "reward": reward,
        "streak": streak,
        "already_claimed": False,
        "balance": balance,
    }


# ── Transaction history ──

async def list_transactions(
    session: AsyncSession,
    user_id: UUID,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[TokenTransaction], int]:
    """Paginated transaction history for a user."""
    q = (
        select(TokenTransaction)
        .where(TokenTransaction.user_id == user_id)
        .order_by(TokenTransaction.created_at.desc())
    )
    total = (await session.execute(
        select(func.count()).select_from(q.subquery())
    )).scalar_one()

    rows = (
        (await session.execute(q.offset((page - 1) * page_size).limit(page_size)))
        .scalars()
        .all()
    )
    return list(rows), total
