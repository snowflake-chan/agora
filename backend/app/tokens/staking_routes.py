"""Staking API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.db.models import User
from app.deps import check_not_banned
from app.tokens import staking as staking_service
from app.users.deps import current_user

router = APIRouter(prefix="/staking", tags=["staking"])


class StakeRequest(BaseModel):
    amount: int
    pool_type: str  # "treasury" | "guild" | "proposal"
    reference_id: UUID | None = None  # guild_id or proposal_id


class UnstakeRequest(BaseModel):
    stake_id: UUID


@router.get("/pools")
async def list_pools():
    """List available staking pools with descriptions."""
    return {
        "pools": [
            {
                "type": key,
                "name": cfg["name"],
                "description": cfg["description"],
                "base_apy": cfg["base_apy"],
                "lock_days": cfg["lock_days"],
                "risk_level": cfg["risk_level"],
                "min_stake": cfg["min_stake"],
            }
            for key, cfg in staking_service.POOL_CONFIG.items()
        ]
    }


@router.post("/stake")
async def create_stake(
    body: StakeRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Stake AGC into a pool."""
    await check_not_banned(user.id, session)
    try:
        stake_row = await staking_service.stake(
            session, user.id, body.amount, body.pool_type, body.reference_id
        )
        await session.commit()
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc))

    return {
        "ok": True,
        "stake": {
            "id": str(stake_row.id),
            "amount": stake_row.amount,
            "pool_type": stake_row.pool_type,
            "apy": stake_row.apy,
            "locked_until": stake_row.locked_until.isoformat() if stake_row.locked_until else None,
            "created_at": stake_row.created_at.isoformat(),
        },
    }


@router.post("/unstake")
async def unstake_stake(
    body: UnstakeRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Withdraw a stake and all pending yield."""
    await check_not_banned(user.id, session)
    try:
        result = await staking_service.unstake(session, body.stake_id, user.id)
        await session.commit()
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc))

    return {"ok": True, **result}


@router.post("/claim-yield")
async def claim_stake_yield(
    body: UnstakeRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Claim pending yield from a stake without unstaking."""
    await check_not_banned(user.id, session)
    try:
        result = await staking_service.claim_yield(session, body.stake_id, user.id)
        await session.commit()
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc))

    return {"ok": True, **result}


@router.get("/my-stakes")
async def list_my_stakes(
    include_inactive: bool = Query(False),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """List all stakes for the current user."""
    stakes = await staking_service.list_user_stakes(session, user.id, include_inactive)
    return {"stakes": stakes}


@router.get("/my-stats")
async def my_staking_stats(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Get aggregate staking stats for the current user."""
    stats = await staking_service.get_user_staking_stats(session, user.id)
    return stats


@router.get("/user-stats/{user_id}")
async def user_staking_stats(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get aggregate staking stats for any user (public)."""
    stats = await staking_service.get_user_staking_stats(session, user_id)
    return stats