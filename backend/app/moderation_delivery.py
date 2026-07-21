"""Recoverable delivery of side effects after a moderation decision."""

import asyncio
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload, lazyload, selectinload

from app.content_moderation import (
    announce_content_published,
    notify_content_reviewed,
)
from app.db import async_session
from app.db.models.content import Content


DELIVERABLE_STATUSES = ("approved", "rejected")


async def deliver_moderation_effects(content_id: UUID) -> bool:
    """Deliver one content decision at least once, with idempotent notifications."""
    async with async_session() as session:
        locked_content_id = await session.scalar(
            select(Content.id)
            .where(Content.id == content_id)
            .with_for_update()
        )
        if locked_content_id is None:
            return False
        content = await session.scalar(
            select(Content)
            .options(
                joinedload(Content.author),
                selectinload(Content.parent),
                selectinload(Content.replying_to),
                lazyload(Content.moderation_reviewer),
            )
            .where(Content.id == content_id)
        )
        if (
            content is None
            or content.moderation_status not in DELIVERABLE_STATUSES
            or content.moderation_effects_completed_at is not None
        ):
            return False

        try:
            await notify_content_reviewed(content, required=True)
            if content.moderation_status == "approved":
                await announce_content_published(
                    content,
                    session=session,
                    required=True,
                )
        except Exception:
            # Notification rows that committed before a later failure are
            # deduplicated on retry. Leaving this marker empty is the outbox.
            await session.rollback()
            raise

        content.moderation_effects_completed_at = await session.scalar(
            select(func.clock_timestamp())
        )
        await session.commit()
        return True


async def reconcile_moderation_effects_once(*, limit: int = 100) -> int:
    """Retry persisted decisions whose public side effects are incomplete."""
    async with async_session() as session:
        content_ids = (
            await session.execute(
                select(Content.id)
                .where(
                    Content.moderation_status.in_(DELIVERABLE_STATUSES),
                    Content.moderation_reviewed_at.is_not(None),
                    Content.moderation_effects_completed_at.is_(None),
                )
                .order_by(Content.moderation_reviewed_at.asc(), Content.id.asc())
                .limit(limit)
            )
        ).scalars().all()

    completed = 0
    for content_id in content_ids:
        try:
            completed += int(await deliver_moderation_effects(content_id))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[moderation-delivery] {content_id} retry failed: {exc}")
    return completed


async def reconcile_moderation_effects() -> None:
    """Run one bounded recovery pass during application startup."""
    try:
        completed = await reconcile_moderation_effects_once()
        print(f"[moderation-delivery] Recovered {completed} decision(s).")
    except Exception as exc:
        print(f"[moderation-delivery] Startup recovery failed: {exc}")


async def run_moderation_delivery_scheduler(interval: float) -> None:
    """Retry incomplete decisions independently of incoming requests."""
    while True:
        await asyncio.sleep(max(1.0, interval))
        try:
            await reconcile_moderation_effects_once()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[moderation-delivery] Periodic recovery failed: {exc}")
