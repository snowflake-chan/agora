"""Violation fine service."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ViolationFine, User
from app.tokens import service as token_service


async def issue_fine(
    session: AsyncSession,
    user_id: UUID,
    amount: int,
    reason: str,
    reference_type: str,
    reference_id: UUID | None = None,
    issued_by: UUID | None = None,
    actor_role: str = "",
) -> ViolationFine:
    """Issue a fine to a user for a rule violation."""
    if actor_role and actor_role not in ("super_admin", "moderator"):
        raise ValueError("Insufficient permissions")

    if amount <= 0:
        raise ValueError("Fine amount must be positive")

    if not reason.strip():
        raise ValueError("Reason is required")

    # Verify user exists
    target = await session.get(User, user_id)
    if target is None:
        raise ValueError("User not found")

    fine = ViolationFine(
        user_id=user_id,
        amount=amount,
        reason=reason.strip(),
        reference_type=reference_type,
        reference_id=reference_id,
        issued_by=issued_by,
    )
    session.add(fine)
    await session.flush()
    return fine


async def pay_fine(
    session: AsyncSession,
    fine_id: UUID,
    user_id: UUID,
) -> ViolationFine:
    """Pay a pending fine. Deducts AGC and marks as paid."""
    fine = await session.get(ViolationFine, fine_id)
    if fine is None:
        raise ValueError("Fine not found")
    if fine.user_id != user_id:
        raise ValueError("Not your fine")
    if fine.status != "pending":
        raise ValueError(f"Fine is already {fine.status}")

    # Deduct AGC
    await token_service.spend(session, user_id, fine.amount, "violation_fine")

    fine.status = "paid"
    fine.paid_at = datetime.now(timezone.utc)
    await session.flush()
    return fine


async def cancel_fine(
    session: AsyncSession,
    fine_id: UUID,
    actor_role: str = "",
) -> ViolationFine:
    """Cancel a pending fine (admin action)."""
    if actor_role and actor_role not in ("super_admin", "moderator"):
        raise ValueError("Insufficient permissions")

    fine = await session.get(ViolationFine, fine_id)
    if fine is None:
        raise ValueError("Fine not found")
    if fine.status != "pending":
        raise ValueError(f"Fine is already {fine.status}")

    fine.status = "cancelled"
    await session.flush()
    return fine


async def has_unpaid_fines(
    session: AsyncSession,
    user_id: UUID,
) -> bool:
    """Check if a user has any unpaid fines (blocks posting)."""
    count = (
        await session.execute(
            select(func.count())
            .select_from(ViolationFine)
            .where(
                ViolationFine.user_id == user_id,
                ViolationFine.status == "pending",
            )
        )
    ).scalar_one()
    return count > 0


async def list_fines(
    session: AsyncSession,
    user_id: UUID | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """List fines, optionally filtered by user and status."""
    q = select(ViolationFine)

    if user_id is not None:
        q = q.where(ViolationFine.user_id == user_id)
    if status is not None:
        q = q.where(ViolationFine.status == status)

    q = q.order_by(ViolationFine.issued_at.desc())

    total = (
        await session.execute(
            select(func.count()).select_from(q.subquery())
        )
    ).scalar_one()

    rows = (
        await session.execute(q.offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()

    items = []
    for r in rows:
        fined_user = await session.get(User, r.user_id)
        issuer = await session.get(User, r.issued_by) if r.issued_by else None
        items.append({
            "id": str(r.id),
            "user": {
                "id": str(r.user_id),
                "username": fined_user.username if fined_user else "unknown",
            },
            "amount": r.amount,
            "reason": r.reason,
            "reference_type": r.reference_type,
            "reference_id": str(r.reference_id) if r.reference_id else None,
            "issued_by": {
                "id": str(r.issued_by),
                "username": issuer.username if issuer else "unknown",
            } if issuer else None,
            "status": r.status,
            "issued_at": r.issued_at.isoformat(),
            "paid_at": r.paid_at.isoformat() if r.paid_at else None,
        })

    return items, total