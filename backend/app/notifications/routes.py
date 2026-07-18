import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.db import get_session
from app.db.models.notification import Notification
from app.db.models.user import User
from app.notifications.redis import (
    get_redis,
    get_unread_count,
    reset_unread_count,
    decrement_unread_count,
)
from app.users.deps import current_user

router = APIRouter()


# ── SSE stream ──


@router.get("/stream")
async def notification_stream(
    user: User = Depends(current_user),
):
    """SSE endpoint — each user gets real-time notifications via Redis Pub/Sub."""

    async def event_generator():
        redis = await get_redis()
        pubsub = redis.pubsub()
        channel = f"notif:{user.id}"
        await pubsub.subscribe(channel)

        try:
            while True:
                message = await pubsub.get_message(timeout=30.0)
                if message and message["type"] == "message":
                    yield {
                        "event": "notification",
                        "data": message["data"],
                    }
                else:
                    # Heartbeat to keep the connection alive
                    yield {"comment": "ping"}
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    return EventSourceResponse(event_generator())


# ── CRUD ──


@router.get("")
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """List notifications for the current user, newest first. Includes unread_count."""
    offset = (page - 1) * page_size

    # Count total
    total = await session.scalar(
        select(func.count(Notification.id)).where(
            Notification.recipient_id == user.id
        )
    )

    # Fetch page
    stmt = (
        select(Notification)
        .where(Notification.recipient_id == user.id)
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    items = result.scalars().all()

    # Fast unread count from Redis
    unread_count = await get_unread_count(str(user.id))

    return {
        "items": [
            {
                "id": str(n.id),
                "type": n.type,
                "title": n.title,
                "message": n.message,
                "link": n.link,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
            }
            for n in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "unread_count": unread_count,
    }


@router.get("/unread-count")
async def unread_count(
    user: User = Depends(current_user),
):
    """Fast unread count from Redis (no DB query)."""
    count = await get_unread_count(str(user.id))
    return {"count": count}


@router.patch("/read-all", status_code=204)
async def mark_all_read(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Mark all notifications as read for the current user."""
    await session.execute(
        update(Notification)
        .where(
            Notification.recipient_id == user.id,
            Notification.is_read == False,
        )
        .values(is_read=True)
    )
    await session.commit()
    await reset_unread_count(str(user.id))


@router.patch("/{notification_id}/read", status_code=204)
async def mark_one_read(
    notification_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Mark a single notification as read."""
    stmt = select(Notification).where(
        Notification.id == notification_id,
        Notification.recipient_id == user.id,
    )
    result = await session.execute(stmt)
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=404, detail="NOTIFICATION_NOT_FOUND")

    notif.is_read = True
    await session.commit()
    await decrement_unread_count(str(user.id))
