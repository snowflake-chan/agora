"""Startup reconciliation: retry patches stuck in transitional states."""

from datetime import datetime, timezone

from sqlalchemy import select

from app.db import async_session
from app.db.models.patch import Patch as PatchModel
from app.patches.github import merge_pr


async def reconcile() -> None:
    """Retry any patches stuck in 'passed' or tally expired 'voting' patches."""
    print("[reconcile] Checking patches...")
    try:
        async with async_session() as session:
            # Patches that passed but never merged (crash during deploy)
            passed = (
                await session.execute(
                    select(PatchModel).where(PatchModel.status == "passed")
                )
            ).scalars().all()

            for patch in passed:
                try:
                    await merge_pr(patch.pr_number)
                    patch.status = "merged"
                    print(f"[reconcile] Merged #{patch.pr_number} ({patch.title})")
                except Exception:
                    patch.status = "failed"
                    print(f"[reconcile] Merge FAILED #{patch.pr_number} ({patch.title})")

            # Expired voting patches
            expired = (
                await session.execute(
                    select(PatchModel).where(
                        PatchModel.status == "voting",
                        PatchModel.voting_ends_at < datetime.now(timezone.utc),
                    )
                )
            ).scalars().all()

            for patch in expired:
                from app.patches.routes import _tally

                await _tally(session, patch)
                print(f"[reconcile] Tallied expired #{patch.pr_number} ({patch.title})")

            await session.commit()
    except Exception as e:
        print(f"[reconcile] Error: {e}")

    print("[reconcile] Done.")
