"""User-facing token routes: balance, transactions, tip."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.db.models import User, TokenTransaction
from app.tokens import service as token_service
from app.users.deps import current_user

router = APIRouter()


# ── Schemas ──

class TipRequest(BaseModel):
    post_id: UUID
    amount: int


# ── Routes ──

@router.get("/balance")
async def get_balance(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    row = await token_service.get_balance(session, user.id)
    return {
        "balance": row.balance,
        "total_earned": row.total_earned,
        "total_spent": row.total_spent,
    }


@router.get("/transactions")
async def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    items, total = await token_service.list_transactions(session, user.id, page, page_size)
    return {
        "items": [
            {
                "id": str(t.id),
                "amount": t.amount,
                "type": t.type,
                "source": t.source,
                "reference_id": str(t.reference_id) if t.reference_id else None,
                "balance_after": t.balance_after,
                "created_at": t.created_at.isoformat(),
            }
            for t in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/tip")
async def tip(
    body: TipRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    # Determine the author of the target post
    from app.db.models import Content
    q = select(Content).where(Content.id == body.post_id)
    result = await session.execute(q)
    post = result.scalar_one_or_none()
    if post is None:
        raise HTTPException(404, detail="POST_NOT_FOUND")

    try:
        new_balance = await token_service.tip(
            session, user.id, post.author_id, body.amount, body.post_id
        )
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc))

    return {"ok": True, "balance_after": new_balance}


@router.post("/daily-login")
async def daily_login(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    result = await token_service.daily_login(session, user.id)
    await session.commit()
    return result
