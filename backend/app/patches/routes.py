import asyncio
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import lazyload

from app.config import settings
from app.db import get_session
from app.db.models.patch import Patch as PatchModel, PatchRevision
from app.db.models.content import Content as ContentModel
from app.db.models.post_like import PostLike
from app.db.models.vote import Vote as VoteModel
from app.db.models.user import User
from app.notifications.service import create_notification, notify_followers
from app.posts.realtime import publish_feed_event
from app.content_moderation import (
    announce_content_published,
    assess_content_moderation_after_read,
    content_tree_visibility_clause,
    content_visibility_clause,
    moderation_metadata_for,
    notify_content_pending,
)
from app.schemas.patch import (
    PatchCreate,
    PatchRead,
    PatchRevisionRead,
    PatchUpdate,
    VoteCreate,
    VoteRead,
)
from app.schemas.post import CommentCreate, CommentRead
from app.patches.github import (
    GitHubMergeUncertainError,
    GitHubPullRequestError,
    get_commit_checks,
    get_pull_request,
    merge_pr,
    pull_request_readiness_error,
)
from app.deps import (
    check_not_banned,
    require_content_interactable,
    require_patch_visible,
)
from app.users.deps import current_user, optional_current_user

router = APIRouter()

STANDARD_VOTING_PERIOD_HOURS = 72
ACTIVE_CREATOR_VOTING_PERIOD_HOURS = 24
ACTIVE_CREATOR_LOOKBACK_DAYS = 90


# ── Helpers ──


async def _get_vote_counts(
    session: AsyncSession, patch_id: UUID | str
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


async def _has_recent_merged_patch(
    session: AsyncSession,
    *,
    author_id: UUID,
    current_patch_id: UUID,
    evaluated_at: datetime,
) -> bool:
    """Return whether the author earned the active-creator voting window."""
    cutoff = evaluated_at - timedelta(days=ACTIVE_CREATOR_LOOKBACK_DAYS)
    prior_merged_patch = await session.scalar(
        select(PatchModel.id)
        .where(
            PatchModel.author_id == author_id,
            PatchModel.id != current_patch_id,
            PatchModel.status == "merged",
            PatchModel.updated_at >= cutoff,
            PatchModel.updated_at < evaluated_at,
        )
        .limit(1)
    )
    return prior_merged_patch is not None


async def _tally(session: AsyncSession, patch: PatchModel) -> bool:
    """Atomically tally an expired vote and schedule at most one merge."""
    locked_patch = (
        await session.execute(
            select(
                PatchModel.id,
                PatchModel.status,
                PatchModel.voting_ends_at,
                PatchModel.title,
                PatchModel.pr_number,
            )
            .where(PatchModel.id == patch.id)
            .with_for_update()
        )
    ).one_or_none()
    if locked_patch is None:
        return False

    # A concurrent request may have completed the tally while this session was
    # waiting for the row lock. Keep its already-loaded ORM instance truthful.
    patch.status = locked_patch.status
    patch.voting_ends_at = locked_patch.voting_ends_at
    if (
        locked_patch.status != "voting"
        or locked_patch.voting_ends_at is None
        or locked_patch.voting_ends_at
        > datetime.now(locked_patch.voting_ends_at.tzinfo)
    ):
        return False

    counts = await _get_vote_counts(session, locked_patch.id)
    total = counts["for"] + counts["against"] + counts["abstain"]

    if total > 0 and counts["for"] > total / 2:
        patch.status = "passed"
    else:
        patch.status = "rejected"

    patch_id = str(locked_patch.id)
    patch_title = locked_patch.title
    patch_status = patch.status
    pr_number = locked_patch.pr_number
    await session.commit()

    if patch_status == "passed":
        asyncio.create_task(
            _do_merge_and_deploy(patch_id, pr_number, patch_title)
        )

    await publish_feed_event(
        "updated",
        item_type="patch",
        item_id=patch_id,
    )
    # Notify voters + author (fire-and-forget)
    asyncio.create_task(
        _notify_patch_voters(patch_id, patch_title, patch_status)
    )

    return True


async def _notify_patch_voters(patch_id: str, patch_title: str, result: str) -> None:
    """Notify all voters + author of a patch vote result (background, own session)."""
    from app.db import async_session as _async_session

    info = {
        "passed": ("vote_passed", "Vote passed", f"Change \"{patch_title}\" passed its vote"),
        "rejected": ("vote_rejected", "Vote rejected", f"Change \"{patch_title}\" did not pass its vote"),
        "merged": ("patch_merged", "Change merged", f"Change \"{patch_title}\" was merged into the main branch"),
        "failed": ("patch_failed", "Merge failed", f"Change \"{patch_title}\" could not be merged"),
    }
    notif_type, title, message = info.get(result, ("unknown", "Change status updated", ""))
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
    """Serialize merge recovery, persist its outcome, then deploy once."""
    from app.db import async_session as _async_session

    try:
        async with _async_session() as session:
            stmt = (
                select(PatchModel)
                .options(lazyload(PatchModel.author))
                .where(PatchModel.id == patch_id)
                .with_for_update()
            )
            result = await session.execute(stmt)
            patch = result.scalar_one_or_none()
            if patch is None or patch.status != "passed":
                return

            patch_title = patch.title
            pr_number = patch.pr_number
            expected_head_sha = patch.submitted_head_sha
            if not expected_head_sha:
                print(
                    f"[merge] Refusing PR #{pr_number}: governed head SHA is missing"
                )
                patch.status = "failed"
                await session.commit()
                outcome = patch.status
            else:
                try:
                    pull_request = await get_pull_request(pr_number)
                    current_head_sha = pull_request.get("head", {}).get("sha")
                    if current_head_sha != expected_head_sha:
                        raise RuntimeError("PULL_REQUEST_HEAD_CHANGED")

                    if pull_request.get("merged") or pull_request.get("merged_at"):
                        patch.status = "merged"
                    else:
                        commit_checks = await get_commit_checks(expected_head_sha)
                        readiness_error = pull_request_readiness_error(
                            pull_request,
                            commit_checks,
                        )
                        if readiness_error in (
                            "PULL_REQUEST_READINESS_PENDING",
                            "PULL_REQUEST_CHECKS_PENDING",
                        ):
                            print(
                                f"[merge] PR #{pr_number} is temporarily pending: "
                                f"{readiness_error}"
                            )
                            return
                        if readiness_error:
                            raise RuntimeError(readiness_error)
                        await merge_pr(
                            pr_number,
                            expected_head_sha=expected_head_sha,
                        )
                        patch.status = "merged"
                except GitHubPullRequestError as exc:
                    # A transient lookup failure has no truthful terminal result.
                    # Leave the proposal passed so startup reconciliation can retry.
                    print(f"[merge] GitHub lookup unavailable for PR #{pr_number}: {exc}")
                    return
                except GitHubMergeUncertainError as exc:
                    print(f"[merge] Outcome unknown for PR #{pr_number}: {exc}")
                    return
                except Exception as exc:
                    print(f"[merge] ERROR merging PR #{pr_number}: {exc}")
                    patch.status = "failed"
                await session.commit()
                outcome = patch.status
    except Exception as status_exc:
        print(f"[merge] ERROR recording outcome for PR #{pr_number}: {status_exc}")
        return

    await publish_feed_event(
        "updated",
        item_type="patch",
        item_id=patch_id,
    )
    asyncio.create_task(
        _notify_patch_voters(patch_id, patch_title or "Unknown", outcome)
    )
    if outcome != "merged":
        return

    # The PR is already merged at this point. A deployment launch failure must
    # not rewrite the truthful governance state to "merge failed".
    try:
        await _trigger_deploy()
    except Exception as deploy_exc:
        print(f"[deploy] ERROR after merging PR #{pr_number}: {deploy_exc}")


async def _auto_tally(session: AsyncSession, patch: PatchModel) -> bool:
    """If voting period has ended, tally and merge. Returns True if status changed."""
    if patch.status != "voting" or not patch.voting_ends_at:
        return False
    if patch.voting_ends_at > datetime.now(patch.voting_ends_at.tzinfo):
        return False
    return await _tally(session, patch)


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
    """Launch the detached deployment helper and verify it started."""
    if not settings.DEPLOY_ENABLED:
        print("[deploy] Disabled by configuration")
        return

    print("[deploy] Launching detached deployment helper...")
    process = await asyncio.create_subprocess_exec(
        "/bin/bash", "/repo/deploy.sh",
        env={**os.environ, "REPO_DIR": settings.REPO_DIR},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
    output = stdout.decode(errors="replace").strip()
    error = stderr.decode(errors="replace").strip()
    if output:
        print(output)
    if process.returncode != 0:
        raise RuntimeError(
            f"deployment helper failed to start (exit {process.returncode}): "
            f"{error or output or 'no output'}"
        )
    print("[deploy] Detached deployment helper started")


def _patch_to_read(
    patch: PatchModel,
    counts: dict[str, int] | None = None,
    comment_count: int = 0,
) -> PatchRead:
    c = counts or {"for": 0, "against": 0, "abstain": 0}
    return PatchRead(
        id=patch.id,
        title=patch.title,
        content=patch.content,
        pr_number=patch.pr_number,
        submitted_head_sha=patch.submitted_head_sha,
        status=patch.status,
        author_id=patch.author_id,
        author_username=patch.author.username,
        voting_started_at=patch.voting_started_at,
        voting_ends_at=patch.voting_ends_at,
        voting_period_hours=patch.voting_period_hours,
        voting_window_kind=patch.voting_window_kind,
        for_count=c["for"],
        against_count=c["against"],
        abstain_count=c["abstain"],
        comment_count=comment_count,
        revision_number=patch.revision_number,
        created_at=patch.created_at,
        updated_at=patch.updated_at,
    )


# ── Patches ──


@router.get("", response_model=list[PatchRead])
async def list_patches(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    user: User | None = Depends(optional_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List patches, newest first."""
    offset = (page - 1) * page_size

    where = [PatchModel.status != "draft"]
    if user is not None:
        where = [
            or_(
                PatchModel.status != "draft",
                PatchModel.author_id == user.id,
            )
        ]
    if status:
        where.append(PatchModel.status == status)

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
    now = datetime.now(timezone.utc)
    for p in patches:
        if (
            p.status == "voting"
            and p.voting_ends_at is not None
            and p.voting_ends_at <= now
        ):
            asyncio.create_task(_auto_tally_patch(str(p.id)))

    # Get vote counts
    patch_ids = [str(p.id) for p in patches]
    counts_map: dict[str, dict[str, int]] = {}
    comment_counts: dict = {}
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
        comment_counts = dict(
            (
                await session.execute(
                    select(ContentModel.patch_id, func.count(ContentModel.id))
                    .where(
                        ContentModel.patch_id.in_(patch_ids),
                        ContentModel.type == "comment",
                        content_visibility_clause(user),
                    )
                    .group_by(ContentModel.patch_id)
                )
            ).all()
        )

    return [
        _patch_to_read(p, counts_map.get(str(p.id)), comment_counts.get(p.id, 0))
        for p in patches
    ]


@router.post("", response_model=PatchRead, status_code=201)
async def create_patch(
    data: PatchCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Create a new patch as draft."""
    await check_not_banned(user.id, session, "mute_patch")
    if not data.title.strip():
        raise HTTPException(status_code=422, detail="TITLE_REQUIRED")
    if not data.content.strip():
        raise HTTPException(status_code=422, detail="CONTENT_REQUIRED")
    if data.pr_number < 1:
        raise HTTPException(status_code=422, detail="INVALID_PR_NUMBER")

    existing_stmt = select(PatchModel.id).where(
        PatchModel.pr_number == data.pr_number,
        PatchModel.status.in_(("draft", "voting", "passed")),
    )
    if await session.scalar(existing_stmt):
        raise HTTPException(status_code=409, detail="PATCH_PR_ALREADY_ACTIVE")

    patch = PatchModel(
        title=data.title.strip(),
        content=data.content.strip(),
        pr_number=data.pr_number,
        author_id=user.id,
    )
    session.add(patch)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="PATCH_PR_ALREADY_ACTIVE") from exc
    await session.refresh(patch)

    # Re-fetch with author relationship
    stmt = select(PatchModel).where(PatchModel.id == patch.id)
    result = await session.execute(stmt)
    patch = result.scalar_one()

    return _patch_to_read(patch)


@router.patch("/{patch_id}", response_model=PatchRead)
async def update_patch(
    patch_id: UUID,
    data: PatchUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Edit an owned draft; submission permanently closes this endpoint."""
    fields = data.model_fields_set - {"revision_number"}
    if not fields:
        raise HTTPException(status_code=422, detail="PATCH_UPDATE_REQUIRED")

    # Lock only the base row. Patch.author is eager-loaded, so locking the ORM
    # entity directly can ask PostgreSQL to lock the nullable side of a join.
    locked_id = await session.scalar(
        select(PatchModel.id)
        .where(PatchModel.id == patch_id)
        .with_for_update()
    )
    if locked_id is None:
        raise HTTPException(status_code=404, detail="PATCH_NOT_FOUND")
    patch = await session.scalar(
        select(PatchModel).where(PatchModel.id == locked_id)
    )
    patch = require_patch_visible(patch, user)
    if patch.author_id != user.id:
        raise HTTPException(status_code=403, detail="FORBIDDEN")
    if patch.status != "draft":
        raise HTTPException(status_code=409, detail="PATCH_EDIT_LOCKED")
    if patch.revision_number != data.revision_number:
        raise HTTPException(status_code=409, detail="PATCH_EDIT_CONFLICT")
    await check_not_banned(user.id, session, "mute_patch")

    new_title = patch.title
    new_content = patch.content
    if "title" in fields:
        new_title = data.title.strip() if data.title is not None else ""
        if not new_title:
            raise HTTPException(status_code=422, detail="TITLE_REQUIRED")
        if len(new_title) > 200:
            raise HTTPException(status_code=422, detail="TITLE_TOO_LONG")
    if "content" in fields:
        new_content = data.content.strip() if data.content is not None else ""
        if not new_content:
            raise HTTPException(status_code=422, detail="CONTENT_REQUIRED")
    if new_title == patch.title and new_content == patch.content:
        raise HTTPException(status_code=422, detail="PATCH_NO_CHANGES")

    edited_at = await session.scalar(select(func.clock_timestamp()))
    session.add(
        PatchRevision(
            patch_id=patch.id,
            version=patch.revision_number,
            title=patch.title,
            content=patch.content,
            editor_id=user.id,
            edited_at=edited_at,
        )
    )
    patch.title = new_title
    patch.content = new_content
    patch.revision_number += 1
    patch.updated_at = edited_at
    await session.commit()

    updated = await session.scalar(
        select(PatchModel).where(PatchModel.id == patch.id)
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="PATCH_NOT_FOUND")
    return _patch_to_read(updated)


@router.get(
    "/{patch_id}/history",
    response_model=list[PatchRevisionRead],
)
async def get_patch_history(
    patch_id: UUID,
    user: User | None = Depends(optional_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Expose draft history to its owner/staff and public history to everyone."""
    patch = await session.scalar(
        select(PatchModel).where(PatchModel.id == patch_id)
    )
    patch = require_patch_visible(patch, user, allow_staff=True)
    revisions = (
        await session.execute(
            select(PatchRevision)
            .where(PatchRevision.patch_id == patch.id)
            .order_by(PatchRevision.version.desc())
        )
    ).scalars().all()
    return [PatchRevisionRead.model_validate(item) for item in revisions]


@router.get("/{patch_id}", response_model=PatchRead)
async def get_patch(
    patch_id: UUID,
    user: User | None = Depends(optional_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get a single patch. Auto-tallies if voting period has ended."""
    stmt = select(PatchModel).where(PatchModel.id == patch_id)
    result = await session.execute(stmt)
    patch = result.scalar_one_or_none()
    patch = require_patch_visible(patch, user, allow_staff=True)

    await _auto_tally(session, patch)

    counts = await _get_vote_counts(session, patch_id)
    comment_count = await session.scalar(
        select(func.count(ContentModel.id)).where(
            ContentModel.patch_id == patch.id,
            ContentModel.type == "comment",
            content_visibility_clause(user),
        )
    )
    return _patch_to_read(patch, counts, comment_count or 0)


@router.delete("/{patch_id}", status_code=204)
async def delete_patch(
    patch_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Delete own draft patch."""
    stmt = (
        select(PatchModel)
        .options(lazyload(PatchModel.author))
        .where(PatchModel.id == patch_id)
        .with_for_update()
    )
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
    patch_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Submit for voting and snapshot the server-selected voting window."""
    await check_not_banned(user.id, session, "mute_patch")
    stmt = (
        select(PatchModel)
        .options(lazyload(PatchModel.author))
        .where(PatchModel.id == patch_id)
        .with_for_update()
    )
    result = await session.execute(stmt)
    patch = result.scalar_one_or_none()
    if not patch:
        raise HTTPException(status_code=404, detail="PATCH_NOT_FOUND")
    if patch.author_id != user.id:
        raise HTTPException(status_code=403, detail="FORBIDDEN")
    if patch.status != "draft":
        raise HTTPException(status_code=422, detail="PATCH_NOT_DRAFT")

    if patch.revision_number > 1:
        moderation = await assess_content_moderation(patch.title, patch.content)
        if moderation.status != "published":
            raise HTTPException(
                status_code=422, detail="PATCH_CONTENT_REVIEW_REQUIRED"
            )

    # A proposal must still point to mergeable work when voting starts. Keep
    # draft creation available in installations that have not connected GitHub.
    submitted_head_sha: str | None = None
    if settings.GITHUB_REPO:
        try:
            pull_request = await get_pull_request(patch.pr_number)
        except GitHubPullRequestError as exc:
            detail = str(exc)
            if detail == "PULL_REQUEST_NOT_FOUND":
                raise HTTPException(status_code=422, detail=detail) from exc
            raise HTTPException(
                status_code=502, detail="GITHUB_PR_LOOKUP_FAILED"
            ) from exc

        head_sha = pull_request.get("head", {}).get("sha")
        if not head_sha:
            raise HTTPException(status_code=502, detail="GITHUB_PR_LOOKUP_FAILED")
        submitted_head_sha = head_sha
        try:
            commit_checks = await get_commit_checks(head_sha)
        except GitHubPullRequestError as exc:
            raise HTTPException(
                status_code=502, detail="GITHUB_CHECK_LOOKUP_FAILED"
            ) from exc

        readiness_error = pull_request_readiness_error(
            pull_request,
            commit_checks,
        )
        if readiness_error:
            status_code = (
                409
                if readiness_error in (
                    "PULL_REQUEST_READINESS_PENDING",
                    "PULL_REQUEST_CHECKS_PENDING",
                )
                else 422
            )
            raise HTTPException(status_code=status_code, detail=readiness_error)

    now = datetime.now(timezone.utc)
    active_creator = await _has_recent_merged_patch(
        session,
        author_id=user.id,
        current_patch_id=patch.id,
        evaluated_at=now,
    )
    voting_period_hours = (
        ACTIVE_CREATOR_VOTING_PERIOD_HOURS
        if active_creator
        else STANDARD_VOTING_PERIOD_HOURS
    )

    patch.status = "voting"
    patch.submitted_head_sha = submitted_head_sha
    patch.voting_started_at = now
    patch.voting_period_hours = voting_period_hours
    patch.voting_window_kind = (
        "active_creator" if active_creator else "standard"
    )
    patch.voting_ends_at = now + timedelta(hours=voting_period_hours)
    await session.commit()

    response_patch = await session.scalar(
        select(PatchModel).where(PatchModel.id == patch.id)
    )

    await publish_feed_event(
        "created",
        item_type="patch",
        item_id=str(patch.id),
    )
    await notify_followers(
        author_id=user.id,
        type="following_patch",
        title=f"{user.nickname or user.username} proposed a new change",
        message=patch.title,
        link=f"/patches/{patch.id}",
    )
    counts = await _get_vote_counts(session, patch_id)
    return _patch_to_read(response_patch, counts)


# ── Votes ──


@router.post("/{patch_id}/vote", response_model=VoteRead, status_code=201)
async def vote_patch(
    patch_id: UUID,
    data: VoteCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Cast or change a vote on a patch."""
    await check_not_banned(user.id, session)
    if data.choice not in ("for", "against", "abstain"):
        raise HTTPException(status_code=422, detail="INVALID_VOTE_CHOICE")

    # Serialize votes with the expiry tally so a request that acquired the lock
    # before the deadline is counted, while a later request sees the final state.
    stmt = (
        select(PatchModel)
        .options(lazyload(PatchModel.author))
        .where(PatchModel.id == patch_id)
        .with_for_update()
    )
    result = await session.execute(stmt)
    patch = result.scalar_one_or_none()
    patch = require_patch_visible(patch, user)
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
            title="New vote",
            message=f"{user.nickname or user.username} voted \"{data.choice}\" on your change",
            link=f"/patches/{patch.id}",
        )

    await publish_feed_event(
        "updated",
        item_type="patch",
        item_id=str(patch.id),
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
    patch_id: UUID,
    user: User | None = Depends(optional_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List all votes for a patch."""
    # Verify patch exists
    patch_stmt = select(PatchModel).where(PatchModel.id == patch_id)
    patch_result = await session.execute(patch_stmt)
    require_patch_visible(
        patch_result.scalar_one_or_none(),
        user,
        allow_staff=True,
    )

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


# ── Discussion ──


@router.get("/{patch_id}/comments", response_model=list[CommentRead])
async def list_patch_comments(
    patch_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(optional_current_user),
):
    allow_staff = bool(user and user.role in ("moderator", "super_admin"))
    patch = await session.scalar(
        select(PatchModel).where(PatchModel.id == patch_id)
    )
    patch = require_patch_visible(patch, user, allow_staff=True)

    comments = (
        await session.execute(
            select(ContentModel)
            .where(
                ContentModel.patch_id == patch.id,
                ContentModel.type == "comment",
                content_tree_visibility_clause(user, allow_staff=allow_staff),
            )
            .order_by(ContentModel.created_at.asc())
        )
    ).scalars().all()
    comment_ids = [comment.id for comment in comments]
    replying_ids = [comment.replying_id for comment in comments if comment.replying_id]

    trace_rows = []
    if replying_ids:
        trace_rows = (
            await session.execute(
                select(ContentModel.id, User.username, ContentModel.content)
                .join(User, ContentModel.author_id == User.id)
                .where(
                    ContentModel.id.in_(replying_ids),
                    content_visibility_clause(user, allow_staff=allow_staff),
                )
            )
        ).all()
    usernames = {row[0]: row[1] for row in trace_rows}
    trace_content = {row[0]: row[2] for row in trace_rows}

    reply_counts = {}
    like_counts = {}
    liked_ids = set()
    if comment_ids:
        reply_counts = dict(
            (
                await session.execute(
                    select(ContentModel.replying_id, func.count(ContentModel.id))
                    .where(
                        ContentModel.replying_id.in_(comment_ids),
                        content_visibility_clause(user, allow_staff=allow_staff),
                    )
                    .group_by(ContentModel.replying_id)
                )
            ).all()
        )
        like_counts = dict(
            (
                await session.execute(
                    select(PostLike.post_id, func.count(PostLike.id))
                    .where(PostLike.post_id.in_(comment_ids))
                    .group_by(PostLike.post_id)
                )
            ).all()
        )
        if user:
            liked_ids = set(
                (
                    await session.execute(
                        select(PostLike.post_id).where(
                            PostLike.post_id.in_(comment_ids),
                            PostLike.user_id == user.id,
                        )
                    )
                ).scalars()
            )

    return [
        CommentRead(
            id=comment.id,
            content=comment.content,
            author_id=comment.author_id,
            parent_id=patch.id,
            replying_id=comment.replying_id,
            author_username=comment.author.username,
            replying_to_username=usernames.get(comment.replying_id),
            replying_to_content=trace_content.get(comment.replying_id),
            reply_count=reply_counts.get(comment.id, 0),
            like_count=like_counts.get(comment.id, 0),
            liked_by_me=comment.id in liked_ids,
            **moderation_metadata_for(comment, user, allow_staff=allow_staff),
            revision_number=comment.revision_number,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
        )
        for comment in comments
    ]


@router.post("/{patch_id}/comments", response_model=CommentRead, status_code=201)
async def create_patch_comment(
    patch_id: UUID,
    data: CommentCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    await check_not_banned(user.id, session, "mute_patch")
    patch = await session.scalar(
        select(PatchModel).where(PatchModel.id == patch_id)
    )
    patch = require_patch_visible(patch, user)
    if not data.content.strip():
        raise HTTPException(status_code=422, detail="CONTENT_REQUIRED")

    if data.replying_id:
        target = await session.scalar(
            select(ContentModel).where(
                ContentModel.id == data.replying_id,
                ContentModel.patch_id == patch.id,
                ContentModel.type == "comment",
            )
        )
        if not target:
            raise HTTPException(status_code=404, detail="REPLY_TARGET_NOT_FOUND")
        try:
            await require_content_interactable(target, user, session)
        except HTTPException as error:
            if error.detail == "CONTENT_NOT_FOUND":
                raise HTTPException(
                    status_code=404,
                    detail="REPLY_TARGET_NOT_FOUND",
                ) from error
            raise

    moderation = await assess_content_moderation_after_read(
        session,
        data.content,
    )

    # A draft can become inaccessible, or a reply can disappear, while the
    # external semantic review runs. Recheck both under short row locks.
    await check_not_banned(user.id, session, "mute_patch")
    locked_patch_id = await session.scalar(
        select(PatchModel.id)
        .where(PatchModel.id == patch_id)
        .with_for_update()
    )
    if locked_patch_id is None:
        raise HTTPException(status_code=404, detail="PATCH_NOT_FOUND")
    patch = await session.scalar(
        select(PatchModel)
        .options(lazyload(PatchModel.author))
        .where(PatchModel.id == locked_patch_id)
        .execution_options(populate_existing=True)
    )
    patch = require_patch_visible(patch, user)

    if data.replying_id:
        locked_reply_id = await session.scalar(
            select(ContentModel.id)
            .where(
                ContentModel.id == data.replying_id,
                ContentModel.patch_id == patch.id,
                ContentModel.type == "comment",
            )
            .with_for_update()
        )
        if locked_reply_id is None:
            raise HTTPException(status_code=404, detail="REPLY_TARGET_NOT_FOUND")
        target = await session.scalar(
            select(ContentModel)
            .where(ContentModel.id == locked_reply_id)
            .execution_options(populate_existing=True)
        )
        try:
            await require_content_interactable(target, user, session)
        except HTTPException as error:
            if error.detail == "CONTENT_NOT_FOUND":
                raise HTTPException(
                    status_code=404,
                    detail="REPLY_TARGET_NOT_FOUND",
                ) from error
            raise

    comment = ContentModel(
        type="comment",
        content=data.content.strip(),
        patch_id=patch.id,
        replying_id=data.replying_id,
        author_id=user.id,
        moderation_status=moderation.status,
        moderation_reason=moderation.reason,
        published_at=(
            datetime.now(timezone.utc)
            if moderation.status == "published"
            else None
        ),
    )
    session.add(comment)
    await session.commit()
    await session.refresh(comment)

    if comment.moderation_status == "pending_review":
        await notify_content_pending(comment)
    else:
        await announce_content_published(comment, session=session)
    return CommentRead(
        id=comment.id,
        content=comment.content,
        author_id=comment.author_id,
        parent_id=patch.id,
        replying_id=comment.replying_id,
        author_username=comment.author.username,
        replying_to_username=None,
        replying_to_content=None,
        **moderation_metadata_for(comment, user),
        revision_number=comment.revision_number,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )
