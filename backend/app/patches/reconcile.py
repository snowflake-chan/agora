"""Startup and periodic reconciliation for governance transitions."""

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.config import settings
from app.db import async_session
from app.db.models.patch import Patch as PatchModel


async def tally_expired_once() -> None:
    """Tally every expired proposal using an independent transaction."""
    from app.patches.routes import _tally

    async with async_session() as lookup_session:
        expired_ids = (
            await lookup_session.execute(
                select(PatchModel.id).where(
                    PatchModel.status == "voting",
                    PatchModel.voting_ends_at.is_not(None),
                    PatchModel.voting_ends_at <= datetime.now(timezone.utc),
                )
            )
        ).scalars().all()

    for patch_id in expired_ids:
        async with async_session() as session:
            patch = await session.scalar(
                select(PatchModel).where(
                    PatchModel.id == patch_id,
                    PatchModel.status == "voting",
                )
            )
            if patch is not None:
                await _tally(session, patch)


async def merge_passed_once() -> None:
    """Retry passed proposals whose GitHub outcome was not yet confirmed."""
    from app.patches.routes import _do_merge_and_deploy

    async with async_session() as session:
        passed_ids = (
            await session.execute(
                select(PatchModel.id).where(PatchModel.status == "passed")
            )
        ).scalars().all()

    for patch_id in passed_ids:
        await _do_merge_and_deploy(str(patch_id), 0)


async def reconcile() -> None:
    """Recover passed proposals and tally expired votes once at startup."""
    print("[reconcile] Checking patches...")
    try:
        # Both online tallying and startup recovery use the same row-locking
        # merge path, so a restart cannot race an already-running worker.
        await merge_passed_once()
        await tally_expired_once()
    except Exception as exc:
        print(f"[reconcile] Error: {exc}")

    print("[reconcile] Done.")


async def run_scheduler() -> None:
    """Keep the fixed voting deadline independent of page traffic."""
    interval = max(1.0, settings.GOVERNANCE_POLL_SECONDS)
    while True:
        await asyncio.sleep(interval)
        try:
            await merge_passed_once()
            await tally_expired_once()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"[reconcile] Periodic tally error: {exc}")
