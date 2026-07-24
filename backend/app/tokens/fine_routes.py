"""Violation fine API routes."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.db.models import User
from app.notifications.service import create_notification
from app.tokens import fines as fine_service
from app.users.deps import current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fines", tags=["fines"])


# ── Role-based admin checks (mirrors app.admin.routes to avoid circular import) ──

async def admin_required(user: User = Depends(current_user)):
    if user.role not in ("super_admin", "moderator"):
        raise HTTPException(403, detail="FORBIDDEN")
    return user


async def super_admin_required(user: User = Depends(current_user)):
    if user.role != "super_admin":
        raise HTTPException(403, detail="FORBIDDEN")
    return user


class IssueFineRequest(BaseModel):
    user_id: UUID
    amount: int
    reason: str
    reference_type: str  # "post" | "comment" | "patch" | "general"
    reference_id: UUID | None = None


class PayFineRequest(BaseModel):
    fine_id: UUID


class CancelFineRequest(BaseModel):
    fine_id: UUID


# ── Admin routes ──

@router.post("/issue")
async def issue_fine(
    body: IssueFineRequest,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(admin_required),
):
    """Issue a fine to a user (admin only)."""
    try:
        fine = await fine_service.issue_fine(
            session, body.user_id, body.amount, body.reason,
            body.reference_type, body.reference_id, admin.id, admin.role,
        )
        await session.commit()
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc))

    try:
        await create_notification(
            recipient_id=body.user_id,
            type="fine_issued",
            title="Fine issued",
            message=f"You have been fined {body.amount} AGC: {body.reason or 'No reason provided'}",
            link="/tokens",
        )
    except Exception:
        logger.exception("Failed to notify fined user %s", body.user_id)

    return {
        "ok": True,
        "fine": {
            "id": str(fine.id),
            "user_id": str(fine.user_id),
            "amount": fine.amount,
            "status": fine.status,
        },
    }


@router.post("/cancel")
async def cancel_fine(
    body: CancelFineRequest,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(admin_required),
):
    """Cancel a pending fine (admin only)."""
    try:
        fine = await fine_service.cancel_fine(session, body.fine_id, admin.role)
        await session.commit()
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc))

    return {"ok": True, "status": fine.status}


@router.get("/list")
async def list_fines(
    user_id: UUID | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(admin_required),
):
    """List fines, optionally filtered (admin only)."""
    items, total = await fine_service.list_fines(
        session, user_id=user_id, status=status, page=page, page_size=page_size,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ── User routes ──

@router.post("/pay")
async def pay_fine(
    body: PayFineRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Pay a pending fine. Deducts AGC from user."""
    try:
        fine = await fine_service.pay_fine(session, body.fine_id, user.id)
        await session.commit()
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc))

    return {"ok": True, "status": fine.status}


@router.get("/my")
async def my_fines(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """List fines for the current user."""
    items, total = await fine_service.list_fines(
        session, user_id=user.id, page=page, page_size=page_size,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/check")
async def check_unpaid(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Check if the current user has unpaid fines."""
    has_unpaid = await fine_service.has_unpaid_fines(session, user.id)
    return {"has_unpaid_fines": has_unpaid}