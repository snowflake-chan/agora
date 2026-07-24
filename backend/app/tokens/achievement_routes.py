"""Achievement API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.db.models import User
from app.tokens.achievements import get_user_achievements, sync_achievements
from app.users.deps import current_user

router = APIRouter(prefix="/achievements", tags=["achievements"])


@router.get("/user/{user_id}")
async def user_achievements(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get achievements for any user (public)."""
    return await get_user_achievements(session, user_id)


@router.get("/my")
async def my_achievements(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Get achievements for the current user."""
    return await get_user_achievements(session, user.id)


@router.post("/sync")
async def sync_my_achievements(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Sync achievements for the current user (recalculate and update)."""
    newly_earned = await sync_achievements(session, user.id)
    await session.commit()
    return {"ok": True, "newly_earned": newly_earned}