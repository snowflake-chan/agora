from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.db.models.patch import Patch as PatchModel
from app.db.models.vote import Vote as VoteModel
from app.db.models.user import User
from app.schemas.patch import (
    PatchCreate,
    PatchRead,
    VoteCreate,
    VoteRead,
)
from app.patches.github import merge_pr
from app.users.deps import current_user

router = APIRouter()


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

    # Get vote counts for all fetched patches
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
    """Get a single patch."""
    stmt = select(PatchModel).where(PatchModel.id == patch_id)
    result = await session.execute(stmt)
    patch = result.scalar_one_or_none()
    if not patch:
        raise HTTPException(status_code=404, detail="PATCH_NOT_FOUND")

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
    """Submit a draft patch for voting (draft → voting)."""
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
    await session.commit()

    counts = await _get_vote_counts(session, patch_id)
    return _patch_to_read(patch, counts)


@router.post("/{patch_id}/close", response_model=PatchRead)
async def close_patch(
    patch_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Close voting, tally votes, and merge if passed (voting → passed/merged/rejected/failed)."""
    stmt = select(PatchModel).where(PatchModel.id == patch_id)
    result = await session.execute(stmt)
    patch = result.scalar_one_or_none()
    if not patch:
        raise HTTPException(status_code=404, detail="PATCH_NOT_FOUND")
    if patch.author_id != user.id:
        raise HTTPException(status_code=403, detail="FORBIDDEN")
    if patch.status != "voting":
        raise HTTPException(status_code=422, detail="PATCH_NOT_VOTING")

    counts = await _get_vote_counts(session, patch_id)
    total = counts["for"] + counts["against"] + counts["abstain"]

    if total > 0 and counts["for"] > total / 2:
        # Passed — try to merge
        patch.status = "passed"
        await session.commit()

        try:
            await merge_pr(patch.pr_url)
            patch.status = "merged"
        except Exception:
            patch.status = "failed"

        await session.commit()
    else:
        patch.status = "rejected"
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
