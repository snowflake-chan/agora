import asyncio
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.db.models.patch import Patch as PatchModel
from app.db.models.vote import Vote as VoteModel
from app.db.models.user import User
from app.notifications.service import create_notification
from app.schemas.patch import (
    PatchCreate,
    PatchRead,
    VoteCreate,
    VoteRead,
)
from app.patches.github import merge_pr
from app.users.deps import current_user

router = APIRouter()

VOTING_PERIOD_DAYS = 3


# ── Helpers ──


async def _get_vote_counts(
    session: AsyncSession, patch_id: str
) -> dict[str, int]:
    """Return for_count, against_count, abstain_count for a patch."""
    rows = (
        await session.execute(
            select(VoteModel.choice, func.count(VoteModel.id))
            .where(VoteModel.patch_id == patch_id)
            .group_by(VoteModel.choice)
        )
    ).all()
    counts = {"for": 0, "against": 0, "abstain": 0}
    for choice, cnt in rows:
        counts[choice] = cnt
    return counts


async def _tally(session: AsyncSession, patch: PatchModel) -> bool:
    """Tally votes. If passed, background merge+deploy. Returns True if status changed."""
    counts = await _get_vote_counts(session, str(patch.id))
    total = counts["for"] + counts["against"] + counts["abstain"]

    if total > 0 and counts["for"] > total / 2:
        patch.status = "passed"
        await session.commit()
        asyncio.create_task(_do_merge_and_deploy(str(patch.id), patch.pr_number))
    else:
        patch.status = "rejected"
        await session.commit()

    # Notify voters + author (fire-and-forget)
    asyncio.create_task(
        _notify_patch_voters(str(patch.id), patch.title, patch.status)
    )

    return True


async def _notify_patch_voters(patch_id: str, patch_title: str, result: str) -> None:
    """Notify all voters + author of a patch vote result (background, own session)."""
    from app.db import async_session as _async_session

    info = {
        "passed": ("vote_passed", "投票通过", f"变更《{patch_title}》投票已通过"),
        "rejected": ("vote_rejected", "投票未通过", f"变更《{patch_title}》投票未通过"),
        "merged": ("patch_merged", "变更已合并", f"变更《{patch_title}》已合并到主分支"),
        "failed": ("patch_failed", "变更合并失败", f"变更《{patch_title}》合并失败，请检查"),
    }
    notif_type, title, message = info.get(result, ("unknown", "变更状态更新", ""))
    try:
        async with _async_session() as session:
            vote_stmt = select(VoteModel.voter_id).where(VoteModel.patch_id == patch_id)
            vote_result = await session.execute(vote_stmt)
            voter_ids = [row[0] for row in vote_result]
            patch_stmt = select(PatchModel.author_id).where(PatchModel.id == patch_id)
            author_id = await session.scalar(patch_stmt)
            recipients = set(voter_ids)
            if author_id:
                recipients.add(author_id)
        for rid in recipients:
            await create_notification(
                recipient_id=rid, type=notif_type,
                title=title, message=message,
                link=f"/patches/{patch_id}",
            )
    except Exception as e:
        print(f"[notif] patch voters error: {e}")


async def _do_merge_and_deploy(patch_id: str, pr_number: int, patch_title: str | None = None) -> None:
    """Merge PR via GitHub and trigger deploy (background task, own session)."""
    from app.db import async_session as _async_session

    try:
        await merge_pr(pr_number)
        async with _async_session() as session:
            stmt = select(PatchModel).where(PatchModel.id == patch_id)
            result = await session.execute(stmt)
            patch = result.scalar_one()
            patch_title = patch.title
            patch.status = "merged"
            await session.commit()
        await _trigger_deploy()
        # Notify voters + author
        asyncio.create_task(
            _notify_patch_voters(patch_id, patch_title, "merged")
        )
    except Exception:
        try:
            async with _async_session() as session:
                stmt = select(PatchModel).where(PatchModel.id == patch_id)
                result = await session.execute(stmt)
                patch = result.scalar_one()
                patch_title = patch.title
                patch.status = "failed"
                await session.commit()
        except Exception:
            patch_title = patch_title or "未知"
        # Notify voters + author
        asyncio.create_task(
            _notify_patch_voters(patch_id, patch_title, "failed")
        )


async def _auto_tally(session: AsyncSession, patch: PatchModel) -> bool:
    """If voting period has ended, tally and merge. Returns True if status changed."""
    if patch.status != "voting" or not patch.voting_ends_at:
        return False
    if patch.voting_ends_at > datetime.now(patch.voting_ends_at.tzinfo):
        return False
    await _tally(session, patch)
    return True


async def _auto_tally_patch(patch_id: str) -> None:
    """Background task: auto-tally a single patch in its own session."""
    from app.db import async_session as _as

    try:
        async with _as() as session:
            stmt = select(PatchModel).where(PatchModel.id == patch_id)
            result = await session.execute(stmt)
            patch = result.scalar_one_or_none()
            if patch and patch.status == "voting" and patch.voting_ends_at:
                if patch.voting_ends_at <= datetime.now(patch.voting_ends_at.tzinfo):
                    await _tally(session, patch)
    except Exception as e:
        print(f"[tally] background tally error for {patch_id}: {e}")


async def _trigger_deploy() -> None:
    """Run deploy.sh (spawn subprocess, don't await — it self-destructs)."""
    if not settings.DEPLOY_ENABLED:
        return

    print("[deploy] Launching deploy.sh (container will self-destruct)...")
    try:
        process = await asyncio.create_subprocess_exec(
            "/bin/bash", "/repo/deploy.sh",
            env={**os.environ, "REPO_DIR": settings.REPO_DIR},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        # Fire and forget — deploy.sh replaces this container
        async def _log_deploy(proc: asyncio.subprocess.Process) -> None:
            try:
                stdout, stderr = await proc.communicate()
                print(f"[deploy] exit={proc.returncode}: {stdout.decode(errors='replace')}")
            except Exception:
                pass  # expected: container killed before we finish

        asyncio.ensure_future(_log_deploy(process))
    except Exception as e:
        print(f"[deploy] ERROR launching deploy: {e}")


def _patch_to_read(patch: PatchModel, counts: dict[str, int] | None = None) -> PatchRead:
    c = counts or {"for": 0, "against": 0, "abstain": 0}
    return PatchRead(
        id=patch.id,
        title=patch.title,
        content=patch.content,
        pr_number=patch.pr_number,
        status=patch.status,
        author_id=patch.author_id,
        author_username=patch.author.username,
        voting_ends_at=patch.voting_ends_at,
        for_count=c["for"],
        against_count=c["against"],
        abstain_count=c["abstain"],
        created_at=patch.created_at,
        updated_at=patch.updated_at,
    )


# ── Patches ──


@router.get("", response_model=list[PatchRead])
async def list_patches(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    """List patches, newest first."""
    offset = (page - 1) * page_size

    where = []
    if status:
        where.append(PatchModel.status == status)

    total = await session.scalar(
        select(func.count(PatchModel.id)).where(*where)
    )

    stmt = (
        select(PatchModel)
        .where(*where)
        .order_by(PatchModel.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    patches = result.scalars().all()

    # Auto-tally any stale voting patches (fire-and-forget so list never blocks)
    for p in patches:
        if p.status == "voting" and p.voting_ends_at:
            asyncio.create_task(_auto_tally_patch(str(p.id)))

    # Get vote counts
    patch_ids = [str(p.id) for p in patches]
    counts_map: dict[str, dict[str, int]] = {}
    if patch_ids:
        rows = (
            await session.execute(
                select(VoteModel.patch_id, VoteModel.choice, func.count(VoteModel.id))
                .where(VoteModel.patch_id.in_(patch_ids))
                .group_by(VoteModel.patch_id, VoteModel.choice)
            )
        ).all()
        for pid, choice, cnt in rows:
            key = str(pid)
            if key not in counts_map:
                counts_map[key] = {"for": 0, "against": 0, "abstain": 0}
            counts_map[key][choice] = cnt

    return [_patch_to_read(p, counts_map.get(str(p.id))) for p in patches]


@router.post("", response_model=PatchRead, status_code=201)
async def create_patch(
    data: PatchCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Create a new patch as draft."""
    from app.deps import check_not_banned
    await check_not_banned(user.id, session, "mute_patch")
    if not data.title.strip():
        raise HTTPException(status_code=422, detail="TITLE_REQUIRED")
    if not data.content.strip():
        raise HTTPException(status_code=422, detail="CONTENT_REQUIRED")
    if data.pr_number < 1:
        raise HTTPException(status_code=422, detail="INVALID_PR_NUMBER")

    patch = PatchModel(
        title=data.title.strip(),
        content=data.content.strip(),
        pr_number=data.pr_number,
        author_id=user.id,
    )
    session.add(patch)
    await session.commit()
    await session.refresh(patch)

    # Re-fetch with author relationship
    stmt = select(PatchModel).where(PatchModel.id == patch.id)
    result = await session.execute(stmt)
    patch = result.scalar_one()

    return _patch_to_read(patch)


@router.get("/{patch_id}", response_model=PatchRead)
async def get_patch(
    patch_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get a single patch. Auto-tallies if voting period has ended."""
    stmt = select(PatchModel).where(PatchModel.id == patch_id)
    result = await session.execute(stmt)
    patch = result.scalar_one_or_none()
    if not patch:
        raise HTTPException(status_code=404, detail="PATCH_NOT_FOUND")

    await _auto_tally(session, patch)

    counts = await _get_vote_counts(session, patch_id)
    return _patch_to_read(patch, counts)


@router.delete("/{patch_id}", status_code=204)
async def delete_patch(
    patch_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Delete own draft patch."""
    stmt = select(PatchModel).where(PatchModel.id == patch_id)
    result = await session.execute(stmt)
    patch = result.scalar_one_or_none()
    if not patch:
        raise HTTPException(status_code=404, detail="PATCH_NOT_FOUND")
    if patch.author_id != user.id:
        raise HTTPException(status_code=403, detail="FORBIDDEN")
    if patch.status != "draft":
        raise HTTPException(status_code=422, detail="PATCH_NOT_DRAFT")

    await session.delete(patch)
    await session.commit()


@router.post("/{patch_id}/submit", response_model=PatchRead)
async def submit_patch(
    patch_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Submit for voting with a 3-day voting period (draft → voting)."""
    from app.deps import check_not_banned
    await check_not_banned(user.id, session, "mute_patch")
    stmt = select(PatchModel).where(PatchModel.id == patch_id)
    result = await session.execute(stmt)
    patch = result.scalar_one_or_none()
    if not patch:
        raise HTTPException(status_code=404, detail="PATCH_NOT_FOUND")
    if patch.author_id != user.id:
        raise HTTPException(status_code=403, detail="FORBIDDEN")
    if patch.status != "draft":
        raise HTTPException(status_code=422, detail="PATCH_NOT_DRAFT")

    patch.status = "voting"
    now = datetime.now(timezone.utc)
    patch.voting_ends_at = now + timedelta(days=VOTING_PERIOD_DAYS)
    await session.commit()

    counts = await _get_vote_counts(session, patch_id)
    return _patch_to_read(patch, counts)


# ── Votes ──


@router.post("/{patch_id}/vote", response_model=VoteRead, status_code=201)
async def vote_patch(
    patch_id: str,
    data: VoteCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Cast or change a vote on a patch."""
    if data.choice not in ("for", "against", "abstain"):
        raise HTTPException(status_code=422, detail="INVALID_VOTE_CHOICE")

    stmt = select(PatchModel).where(PatchModel.id == patch_id)
    result = await session.execute(stmt)
    patch = result.scalar_one_or_none()
    if not patch:
        raise HTTPException(status_code=404, detail="PATCH_NOT_FOUND")
    if patch.status != "voting":
        raise HTTPException(status_code=422, detail="PATCH_NOT_VOTING")

    # Reject if voting period has ended
    if patch.voting_ends_at and patch.voting_ends_at < datetime.now(patch.voting_ends_at.tzinfo):
        raise HTTPException(status_code=422, detail="VOTING_ALREADY_ENDED")

    # Upsert vote
    vote_stmt = select(VoteModel).where(
        VoteModel.patch_id == patch_id,
        VoteModel.voter_id == user.id,
    )
    existing = await session.scalar(vote_stmt)
    if existing:
        existing.choice = data.choice
        vote = existing
    else:
        vote = VoteModel(
            patch_id=patch.id,
            voter_id=user.id,
            choice=data.choice,
        )
        session.add(vote)

    await session.commit()
    await session.refresh(vote)

    # Notify patch author (unless voting on your own patch)
    if patch.author_id != user.id:
        await create_notification(
            recipient_id=patch.author_id,
            type="vote",
            title="新投票",
            message=f"{user.nickname or user.username} 对你的变更投了「{data.choice}」",
            link=f"/patches/{patch.id}",
        )

    return VoteRead(
        id=vote.id,
        patch_id=vote.patch_id,
        voter_id=vote.voter_id,
        choice=vote.choice,
        voter_username=vote.voter.username,
        created_at=vote.created_at,
    )


@router.get("/{patch_id}/votes", response_model=list[VoteRead])
async def list_votes(
    patch_id: str,
    session: AsyncSession = Depends(get_session),
):
    """List all votes for a patch."""
    # Verify patch exists
    patch_stmt = select(PatchModel).where(PatchModel.id == patch_id)
    patch_result = await session.execute(patch_stmt)
    if not patch_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="PATCH_NOT_FOUND")

    stmt = (
        select(VoteModel)
        .where(VoteModel.patch_id == patch_id)
        .order_by(VoteModel.created_at.desc())
    )
    result = await session.execute(stmt)
    votes = result.scalars().all()

    return [
        VoteRead(
            id=v.id,
            patch_id=v.patch_id,
            voter_id=v.voter_id,
            choice=v.choice,
            voter_username=v.voter.username,
            created_at=v.created_at,
        )
        for v in votes
    ]
