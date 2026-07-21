from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import lazyload, selectinload

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.ai.client import request_structured_completion
from app.ai.errors import AIServiceError
from app.ai.runtime_config import (
    AI_PROVIDER_SETTING_KEY,
    AIRuntimeConfig,
    get_ai_runtime_config,
    invalidate_ai_runtime_config,
    serialize_database_config,
)
from app.config import settings
from app.content_moderation import (
    REVIEWABLE_MODERATION_STATUSES,
    content_is_public,
    content_href,
)
from app.deps import (
    check_not_banned,
    require_content_interactable,
    require_patch_visible,
)
from app.db import get_session
from app.db.models.content import Content as ContentModel
from app.db.models.guild import Guild, GuildMember
from app.db.models.moderation import BanRecord, Report
from app.db.models.patch import Patch as PatchModel
from app.db.models.post_poll import PostPoll
from app.db.models.settings import SiteSetting
from app.db.models.user import User
from app.moderation_delivery import deliver_moderation_effects
from app.posts.realtime import publish_feed_event
from app.schemas.moderation import ContentReviewDecision, ReportCreate
from app.users.deps import current_user

router = APIRouter()

# ── Role-based admin check ──

async def admin_required(user: User = Depends(current_user)):
    if user.role not in ("super_admin", "moderator"):
        raise HTTPException(403, detail="FORBIDDEN")
    return user


async def super_admin_required(user: User = Depends(current_user)):
    if user.role != "super_admin":
        raise HTTPException(403, detail="FORBIDDEN")
    return user


def _content_review_item(content: ContentModel) -> dict:
    poll = content.poll if content.type == "post" else None
    return {
        "id": content.id,
        "content_id": content.id,
        "content_type": content.type,
        "title": content.title,
        "content": content.content,
        "revision_number": content.revision_number,
        "author_id": content.author_id,
        "author_username": content.author.username if content.author else "",
        "moderation_status": content.moderation_status,
        "moderation_reason": content.moderation_reason,
        "moderation_review_note": content.moderation_review_note,
        "moderation_reviewed_by": content.moderation_reviewed_by,
        "moderation_reviewed_at": content.moderation_reviewed_at,
        "created_at": content.created_at,
        "target_href": content_href(content),
        "parent_id": content.parent_id,
        "patch_id": content.patch_id,
        "guild_id": content.guild_id,
        "poll_question": poll.question if poll is not None else None,
        "poll_options": (
            [option.text for option in poll.options]
            if poll is not None
            else []
        ),
    }


@router.get("/moderation")
async def list_content_reviews(
    status: str = Query("pending_review"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: User = Depends(admin_required),
    session: AsyncSession = Depends(get_session),
):
    if status not in REVIEWABLE_MODERATION_STATUSES:
        raise HTTPException(400, detail="INVALID_MODERATION_STATUS")
    rows = (
        await session.execute(
            select(ContentModel)
            .options(
                selectinload(ContentModel.poll).selectinload(PostPoll.options)
            )
            .where(ContentModel.moderation_status == status)
            .order_by(ContentModel.created_at.asc(), ContentModel.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return [_content_review_item(content) for content in rows]


@router.post("/moderation/{content_id}/review")
async def review_content(
    content_id: UUID,
    body: ContentReviewDecision,
    user: User = Depends(admin_required),
    session: AsyncSession = Depends(get_session),
):
    content = (
        await session.execute(
            select(ContentModel)
            .options(
                lazyload(ContentModel.author),
                lazyload(ContentModel.moderation_reviewer),
            )
            .where(ContentModel.id == content_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if content is None:
        raise HTTPException(404, detail="CONTENT_NOT_FOUND")
    if content.moderation_status != "pending_review":
        raise HTTPException(409, detail="CONTENT_REVIEW_ALREADY_DECIDED")
    expected_revision = body.revision_number or 1
    if content.revision_number != expected_revision:
        raise HTTPException(409, detail="CONTENT_REVIEW_CONFLICT")

    approved = body.decision == "approve"
    first_publication = approved and content.published_at is None
    content.moderation_status = "approved" if approved else "rejected"
    content.moderation_review_note = body.note
    content.moderation_reviewed_by = user.id
    reviewed_at = await session.scalar(
        select(func.clock_timestamp())
    )
    content.moderation_reviewed_at = reviewed_at
    # A previously public item keeps its original feed position while its edit
    # is reviewed. New held submissions begin their public lifetime here.
    if first_publication:
        content.published_at = reviewed_at
    content.moderation_effects_completed_at = None

    # A private poll has not had a real voting window yet. Preserve the
    # author's chosen duration, but start it when the post becomes public.
    if first_publication and content.type == "post":
        poll = await session.scalar(
            select(PostPoll)
            .where(PostPoll.post_id == content.id)
            .with_for_update()
        )
        if poll is not None:
            duration = poll.closes_at - poll.created_at
            poll.created_at = reviewed_at
            poll.closes_at = reviewed_at + duration
    await session.commit()

    # The decision is durable before any external side effect. Delivery takes
    # its own row lock, deduplicates notification rows, and is retried by the
    # startup/periodic reconciler if this request is interrupted.
    try:
        await deliver_moderation_effects(content_id)
    except Exception as exc:
        print(f"[moderation-delivery] immediate delivery failed: {exc}")

    content = await session.scalar(
        select(ContentModel)
        .options(
            selectinload(ContentModel.poll).selectinload(PostPoll.options)
        )
        .where(ContentModel.id == content_id)
    )
    if content is None:
        raise HTTPException(404, detail="CONTENT_NOT_FOUND")
    return _content_review_item(content)


# ═══════════════════════════════════════════
#  Reports
# ═══════════════════════════════════════════


@router.post("/reports")
async def create_report(
    body: ReportCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    content_id = body.content_id
    patch_id = body.patch_id
    reason = body.reason
    await check_not_banned(user.id, session)
    if content_id is None and patch_id is None:
        raise HTTPException(422, detail="REPORT_TARGET_REQUIRED")
    if content_id is not None and patch_id is not None:
        raise HTTPException(422, detail="REPORT_TARGET_AMBIGUOUS")

    normalized_reason = reason.strip()
    if not normalized_reason:
        raise HTTPException(422, detail="REPORT_REASON_REQUIRED")

    if content_id is not None:
        target = (
            await session.execute(
                select(ContentModel)
                .options(
                    lazyload(ContentModel.author),
                    lazyload(ContentModel.parent),
                    lazyload(ContentModel.replying_to),
                )
                .where(ContentModel.id == content_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        target = await require_content_interactable(
            target,
            user,
            session,
            allow_staff=True,
        )
        target_filter = Report.content_id == content_id
    else:
        target = (
            await session.execute(
                select(PatchModel)
                .options(lazyload(PatchModel.author))
                .where(PatchModel.id == patch_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        target = require_patch_visible(target, user, allow_staff=True)
        target_filter = Report.patch_id == patch_id

    if target.author_id == user.id:
        raise HTTPException(403, detail="REPORT_OWN_TARGET_FORBIDDEN")

    dup = (await session.execute(
        select(Report).where(target_filter, Report.reporter_id == user.id)
    )).scalar_one_or_none()
    if dup:
        raise HTTPException(409, detail="REPORT_ALREADY_EXISTS")
    r = Report(
        content_id=content_id,
        patch_id=patch_id,
        reporter_id=user.id,
        reason=normalized_reason,
    )
    session.add(r)
    await session.commit()
    return {
        "ok": True,
        "id": r.id,
        "content_id": r.content_id,
        "patch_id": r.patch_id,
    }


@router.get("/reports")
async def list_reports(
    status: str | None = None,
    user: User = Depends(admin_required),
    session: AsyncSession = Depends(get_session),
):
    q = select(Report).order_by(Report.created_at.desc())
    if status:
        q = q.where(Report.status == status)
    rows = (await session.execute(q)).scalars().all()
    content_ids = [r.content_id for r in rows if r.content_id]
    patch_ids = [r.patch_id for r in rows if r.patch_id]
    report_counts: dict[tuple[str, str], int] = {}
    if content_ids:
        count_rows = (await session.execute(
            select(Report.content_id, func.count(Report.id))
            .where(Report.content_id.in_(content_ids))
            .group_by(Report.content_id)
        )).all()
        report_counts.update(
            {("content", str(target_id)): count for target_id, count in count_rows}
        )
    if patch_ids:
        count_rows = (await session.execute(
            select(Report.patch_id, func.count(Report.id))
            .where(Report.patch_id.in_(patch_ids))
            .group_by(Report.patch_id)
        )).all()
        report_counts.update(
            {("patch", str(target_id)): count for target_id, count in count_rows}
        )

    response = []
    for report in rows:
        target = None
        if report.content_id is not None:
            target_type = "content"
            target_id = report.content_id
            target = report.content
            title = target.title if target else ""
            body = target.content[:200] if target and target.content else ""
            author = target.author if target else None
            if target is None:
                target_href = None
            elif target.type == "post":
                target_href = f"/posts/{target.id}"
            elif target.patch_id is not None:
                target_href = f"/patches/{target.patch_id}#{target.id}"
            elif target.guild_id is not None:
                target_href = f"/guilds/{target.guild_id}#{target.id}"
            elif target.parent_id is not None:
                target_href = f"/posts/{target.parent_id}#{target.id}"
            else:
                target_href = None
        elif report.patch_id is not None:
            target_type = "patch"
            target_id = report.patch_id
            target = report.patch
            title = target.title if target else ""
            body = target.content[:200] if target and target.content else ""
            author = target.author if target else None
            target_href = f"/patches/{target.id}" if target else None
        else:
            target_type = "deleted"
            target_id = None
            title = ""
            body = ""
            author = None
            target_href = None

        response.append(dict(
            id=report.id,
            target_type=target_type,
            target_id=target_id,
            target_href=target_href,
            target_deleted=target is None,
            content_id=report.content_id,
            patch_id=report.patch_id,
            content_title=title,
            content_body=body,
            content_author=author.username if author else "",
            content_author_deleted=author is None,
            content_author_id=str(author.id) if author else "",
            patch_title=report.patch.title if report.patch else None,
            reporter_username=report.reporter.username if report.reporter else "",
            reason=report.reason,
            status=report.status,
            created_at=report.created_at.isoformat(),
            report_count=report_counts.get(
                (target_type, str(target_id)) if target_id else ("deleted", ""),
                1,
            ),
        ))
    return response


@router.post("/reports/{report_id}/resolve")
async def resolve_report(
    report_id: UUID,
    action: str = Query("resolved"),
    user: User = Depends(admin_required),
    session: AsyncSession = Depends(get_session),
):
    if action not in ("resolved", "dismissed", "delete_post", "delete_patch"):
        raise HTTPException(400, detail="INVALID_REPORT_ACTION")
    if action in ("delete_post", "delete_patch") and user.role != "super_admin":
        raise HTTPException(403, detail="FORBIDDEN")

    report_target = (
        await session.execute(
            select(Report.content_id, Report.patch_id)
            .where(Report.id == report_id)
        )
    ).one_or_none()
    if report_target is None:
        raise HTTPException(404, detail="REPORT_NOT_FOUND")
    initial_content_id, initial_patch_id = report_target
    if initial_content_id is not None and initial_patch_id is not None:
        raise HTTPException(409, detail="REPORT_TARGET_INVALID")
    if action == "delete_post" and initial_patch_id is not None:
        raise HTTPException(400, detail="INVALID_REPORT_ACTION")
    if action == "delete_patch" and initial_content_id is not None:
        raise HTTPException(400, detail="INVALID_REPORT_ACTION")

    # Lock the target before locking any report rows. Report creation uses the
    # same target-first order, which prevents both duplicate processing and a
    # report/report deadlock when several reports share one target.
    target_exists = False
    if initial_content_id is not None:
        target_exists = (
            await session.scalar(
                select(ContentModel.id)
                .where(ContentModel.id == initial_content_id)
                .with_for_update()
            )
            is not None
        )
    elif initial_patch_id is not None:
        target_exists = (
            await session.scalar(
                select(PatchModel.id)
                .where(PatchModel.id == initial_patch_id)
                .with_for_update()
            )
            is not None
        )

    if target_exists:
        target_filter = (
            Report.content_id == initial_content_id
            if initial_content_id is not None
            else Report.patch_id == initial_patch_id
        )
        target_reports = (
            await session.execute(
                select(Report)
                .options(
                    lazyload(Report.reporter),
                    lazyload(Report.content),
                    lazyload(Report.patch),
                )
                .where(target_filter)
                .order_by(Report.id)
                .with_for_update()
            )
        ).scalars().all()
        r = next((item for item in target_reports if item.id == report_id), None)
        if r is None:
            raise HTTPException(404, detail="REPORT_NOT_FOUND")
        if r.status != "pending":
            raise HTTPException(409, detail="REPORT_ALREADY_RESOLVED")
        related_reports = [
            item for item in target_reports
            if item.id != report_id and item.status == "pending"
        ]
    else:
        # A deleted target has already had its FK set to NULL. Lock only the
        # tombstone report and re-read its state before deciding the action.
        r = (
            await session.execute(
                select(Report)
                .options(
                    lazyload(Report.reporter),
                    lazyload(Report.content),
                    lazyload(Report.patch),
                )
                .where(Report.id == report_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if r is None:
            raise HTTPException(404, detail="REPORT_NOT_FOUND")
        if r.status != "pending":
            raise HTTPException(409, detail="REPORT_ALREADY_RESOLVED")
        related_reports = []

    content_id = r.content_id
    patch_id = r.patch_id
    if content_id is not None and patch_id is not None:
        raise HTTPException(409, detail="REPORT_TARGET_INVALID")
    if action == "delete_post" and patch_id is not None:
        raise HTTPException(400, detail="INVALID_REPORT_ACTION")
    if action == "delete_patch" and content_id is not None:
        raise HTTPException(400, detail="INVALID_REPORT_ACTION")
    if action in ("delete_post", "delete_patch") and content_id is None and patch_id is None:
        raise HTTPException(409, detail="REPORT_TARGET_GONE")

    r.status = "dismissed" if action == "dismissed" else "resolved"

    for other in related_reports:
        other.status = r.status

    # Persist report state before a target delete can SET NULL the foreign keys.
    await session.flush()
    if action == "delete_post" and content_id is not None:
        content = await session.scalar(
            select(ContentModel).where(ContentModel.id == content_id)
        )
        if content:
            await session.delete(content)
    elif action == "delete_patch" and patch_id is not None:
        patch = await session.scalar(
            select(PatchModel).where(PatchModel.id == patch_id)
        )
        if patch:
            await session.delete(patch)

    await session.commit()
    return {"ok": True, "also_resolved": len(related_reports)}


# ═══════════════════════════════════════════
#  Post / Patch listing (admin)
# ═══════════════════════════════════════════


@router.get("/posts")
async def admin_list_posts(user: User = Depends(admin_required), session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(
        select(ContentModel).where(ContentModel.type == "post", ContentModel.guild_id == None)
        .order_by(ContentModel.created_at.desc()).limit(200)
    )).scalars().all()
    return [dict(
        id=r.id, title=r.title, content=r.content[:300],
        author_username=r.author.username if r.author else "",
        author_id=r.author_id, created_at=r.created_at.isoformat() if r.created_at else "",
        moderation_status=r.moderation_status,
        moderation_reason=r.moderation_reason,
    ) for r in rows]


@router.get("/patches")
async def admin_list_patches(user: User = Depends(admin_required), session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(
        select(PatchModel).order_by(PatchModel.created_at.desc()).limit(200)
    )).scalars().all()
    return [dict(
        id=r.id, title=r.title, pr_number=r.pr_number, status=r.status,
        author_username=r.author.username if r.author else "",
        author_id=r.author_id, created_at=r.created_at.isoformat() if r.created_at else "",
    ) for r in rows]


# ═══════════════════════════════════════════
#  Post / Patch CRUD (admin)
# ═══════════════════════════════════════════


@router.delete("/posts/{post_id}")
async def delete_post_admin(post_id: UUID, user: User = Depends(super_admin_required), session: AsyncSession = Depends(get_session)):
    locked_content_id = await session.scalar(
        select(ContentModel.id)
        .where(ContentModel.id == post_id)
        .with_for_update()
    )
    c = (
        await session.scalar(
            select(ContentModel).where(ContentModel.id == locked_content_id)
        )
        if locked_content_id is not None
        else None
    )
    if not c: raise HTTPException(404)
    was_public = content_is_public(c)
    await session.delete(c); await session.commit()
    if was_public:
        await publish_feed_event("removed", item_type="post", item_id=str(post_id))
    return {"ok": True}


@router.post("/posts/{post_id}/mute")
async def mute_post_admin(post_id: UUID, hours: int = Query(..., ge=1, le=87_600), user: User = Depends(super_admin_required), session: AsyncSession = Depends(get_session)):
    c = (await session.execute(select(ContentModel).where(ContentModel.id == post_id))).scalar_one_or_none()
    if not c: raise HTTPException(404)
    now = datetime.now(timezone.utc)
    br = BanRecord(target_user_id=c.author_id, content_id=c.id, type="mute_post",
                    duration_hours=hours, expires_at=now + timedelta(hours=hours))
    session.add(br); await session.commit()
    return {"ok": True}


@router.post("/users/{user_id}/ban")
async def ban_user(
    user_id: UUID,
    hours: int = Query(..., ge=0, le=87_600),
    type: str = Query("ban_user"),
    reason: str = Query(""),
    user: User = Depends(super_admin_required),
    session: AsyncSession = Depends(get_session),
):
    if type not in ("ban_user", "mute_post", "mute_patch"):
        raise HTTPException(400, detail="INVALID_BAN_TYPE")
    now = datetime.now(timezone.utc)
    br = BanRecord(
        target_user_id=user_id,
        type=type,
        duration_hours=hours if hours > 0 else None,
        expires_at=now + timedelta(hours=hours) if hours > 0 else None,
        reason=reason or None,
    )
    session.add(br); await session.commit()
    return {"ok": True}


@router.get("/users/{user_id}/ban-status")
async def get_ban_status(
    user_id: UUID,
    user: User = Depends(admin_required),
    session: AsyncSession = Depends(get_session),
):
    now = datetime.now(timezone.utc)
    rows = (await session.execute(
        select(BanRecord).where(
            BanRecord.target_user_id == user_id,
            BanRecord.is_active == True,
            or_(BanRecord.expires_at.is_(None), BanRecord.expires_at > now),
        )
    )).scalars().all()
    return [
        dict(
            id=str(r.id), type=r.type, reason=r.reason,
            duration_hours=r.duration_hours,
            expires_at=r.expires_at.isoformat() if r.expires_at else None,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


@router.post("/users/{user_id}/unban")
async def unban_user(
    user_id: UUID,
    type: str | None = Query(None),
    user: User = Depends(super_admin_required),
    session: AsyncSession = Depends(get_session),
):
    q = select(BanRecord).where(BanRecord.target_user_id == user_id, BanRecord.is_active == True)
    if type:
        q = q.where(BanRecord.type == type)
    rows = (await session.execute(q)).scalars().all()
    for br in rows:
        br.is_active = False
    await session.commit()
    return {"ok": True}


@router.delete("/patches/{patch_id}")
async def delete_patch_admin(patch_id: UUID, user: User = Depends(super_admin_required), session: AsyncSession = Depends(get_session)):
    p = (await session.execute(select(PatchModel).where(PatchModel.id == patch_id))).scalar_one_or_none()
    if not p: raise HTTPException(404)
    await session.delete(p); await session.commit()
    return {"ok": True}


# ═══════════════════════════════════════════
#  Guild admin management
# ═══════════════════════════════════════════


@router.patch("/guilds/{guild_id}")
async def admin_update_guild(
    guild_id: UUID,
    name: str | None = Query(None, min_length=1, max_length=80),
    logo: str | None = Query(None, max_length=500),
    description: str | None = Query(None, max_length=2000),
    level: int | None = Query(None, ge=1, le=5),
    user: User = Depends(super_admin_required),
    session: AsyncSession = Depends(get_session),
):
    g = (await session.execute(select(Guild).where(Guild.id == guild_id))).scalar_one_or_none()
    if not g: raise HTTPException(404)
    normalized_name = name.strip() if name is not None else None
    if name is not None and not normalized_name:
        raise HTTPException(422, detail="GUILD_NAME_REQUIRED")
    if normalized_name:
        duplicate_name = await session.scalar(
            select(Guild.id).where(
                Guild.name == normalized_name,
                Guild.id != guild_id,
            )
        )
        if duplicate_name:
            raise HTTPException(409, detail="GUILD_NAME_TAKEN")
        g.name = normalized_name
    if logo is not None: g.logo = logo.strip() or None
    if description is not None: g.description = description.strip() or None
    if level is not None: g.level = level
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, detail="GUILD_NAME_TAKEN") from exc
    return {"ok": True}


@router.delete("/guilds/{guild_id}")
async def admin_delete_guild(guild_id: UUID, user: User = Depends(super_admin_required), session: AsyncSession = Depends(get_session)):
    g = (await session.execute(select(Guild).where(Guild.id == guild_id))).scalar_one_or_none()
    if not g: raise HTTPException(404)
    await session.delete(g); await session.commit()
    return {"ok": True}


@router.delete("/guilds/{guild_id}/members/{member_id}")
async def admin_remove_member(guild_id: UUID, member_id: UUID, user: User = Depends(super_admin_required), session: AsyncSession = Depends(get_session)):
    m = (await session.execute(select(GuildMember).where(GuildMember.guild_id == guild_id, GuildMember.user_id == member_id))).scalar_one_or_none()
    if not m: raise HTTPException(404)
    if m.role == "president":
        raise HTTPException(409, detail="GUILD_PRESIDENT_ROLE_LOCKED")
    await session.delete(m); await session.commit()
    return {"ok": True}


@router.get("/guilds/{guild_id}/discussions")
async def admin_list_discussions(guild_id: UUID, user: User = Depends(super_admin_required), session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(ContentModel).where(ContentModel.guild_id == guild_id, ContentModel.type == "guild_post").order_by(ContentModel.created_at.desc()))).scalars().all()
    return [dict(id=r.id, title=r.title, content=r.content, author_username=r.author.username if r.author else "", created_at=r.created_at.isoformat()) for r in rows]


@router.delete("/guilds/{guild_id}/discussions/{post_id}")
async def admin_delete_discussion(guild_id: UUID, post_id: UUID, user: User = Depends(super_admin_required), session: AsyncSession = Depends(get_session)):
    locked_content_id = await session.scalar(
        select(ContentModel.id).where(
            ContentModel.id == post_id,
            ContentModel.guild_id == guild_id,
            ContentModel.type == "guild_post",
        ).with_for_update()
    )
    c = (
        await session.scalar(
            select(ContentModel).where(ContentModel.id == locked_content_id)
        )
        if locked_content_id is not None
        else None
    )
    if not c: raise HTTPException(404)
    await session.delete(c); await session.commit()
    return {"ok": True}


# ═══════════════════════════════════════════
#  User listing
# ═══════════════════════════════════════════


@router.get("/users")
async def admin_list_users(user: User = Depends(super_admin_required), session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(User))).scalars().all()
    return [
        dict(id=u.id, username=u.username, email=u.email, nickname=u.nickname, is_active=u.is_active,
             role=u.role)
        for u in rows
    ]


@router.post("/users/{user_id}/role")
async def set_user_role(
    user_id: UUID,
    role: str = Query(...),
    user: User = Depends(super_admin_required),
    session: AsyncSession = Depends(get_session),
):
    if role not in ("super_admin", "moderator", "user"):
        raise HTTPException(400, detail="INVALID_ROLE")
    target = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not target:
        raise HTTPException(404)
    target.role = role
    await session.commit()
    return {"ok": True, "role": role}


@router.post("/seed-super-admin")
async def seed_super_admin(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Promote the configured bootstrap account without embedding an identity."""
    configured_email = settings.SUPER_ADMIN_EMAIL.strip().lower()
    if not configured_email:
        raise HTTPException(404, detail="ADMIN_BOOTSTRAP_DISABLED")
    if user.email.strip().lower() != configured_email:
        raise HTTPException(403, detail="FORBIDDEN")
    from sqlalchemy import update
    await session.execute(
        update(User).where(User.id == user.id).values(role="super_admin")
    )
    await session.commit()
    return {"ok": True}


# ── AI provider settings ──

class AdminAIProbeResponse(BaseModel):
    ok: bool


class AdminAISettingsUpdate(BaseModel):
    enabled: bool = False
    base_url: str = Field(default="", max_length=500)
    model: str = Field(default="", max_length=200)
    api_key: str | None = Field(default=None, max_length=1000)
    moderation_provider_fallback_enabled: bool = False


def _admin_ai_settings_response(config: AIRuntimeConfig) -> dict:
    return {
        "enabled": config.enabled,
        "base_url": config.base_url,
        "model": config.model,
        "api_key_configured": bool(config.api_key),
        "moderation_provider_fallback_enabled": config.moderation_provider_fallback_enabled,
        "trusted_classifier_configured": bool(settings.AI_POLITICAL_CLASSIFIER_URL.strip()),
        "source": config.source,
    }


@router.get("/ai-settings")
async def get_admin_ai_settings(_user: User = Depends(super_admin_required)):
    config = await get_ai_runtime_config(force_refresh=True)
    return _admin_ai_settings_response(config)


@router.post("/ai-settings/test")
async def test_admin_ai_settings(
    data: AdminAISettingsUpdate,
    _user: User = Depends(super_admin_required),
):
    current = await get_ai_runtime_config(force_refresh=True)
    base_url = data.base_url.strip().rstrip("/")
    model = data.model.strip()
    api_key = current.api_key if data.api_key is None else data.api_key.strip()
    if not base_url.startswith(("http://", "https://")):
        raise HTTPException(422, detail="AI_BASE_URL_INVALID")
    if settings.is_production() and not base_url.startswith("https://"):
        raise HTTPException(422, detail="AI_BASE_URL_HTTPS_REQUIRED")
    if not (api_key and base_url and model):
        raise HTTPException(422, detail="AI_PROVIDER_CONFIG_INCOMPLETE")
    candidate = AIRuntimeConfig(
        enabled=True,
        api_key=api_key,
        base_url=base_url,
        model=model,
        moderation_provider_fallback_enabled=(
            data.moderation_provider_fallback_enabled
        ),
        source="database",
    )
    try:
        result = await request_structured_completion(
            user_message='{"task":"connection_test","output_schema":{"ok":true}}',
            response_type=AdminAIProbeResponse,
            max_tokens=16,
            system_prompt=(
                'Return exactly {"ok":true} as JSON. Do not add commentary.'
            ),
            runtime_config=candidate,
        )
    except AIServiceError as exc:
        raise HTTPException(502, detail="AI_CONNECTION_TEST_FAILED") from exc
    if result.ok is not True:
        raise HTTPException(502, detail="AI_CONNECTION_TEST_FAILED")
    return {"ok": True}


@router.put("/ai-settings")
async def set_admin_ai_settings(
    data: AdminAISettingsUpdate,
    _user: User = Depends(super_admin_required),
    session: AsyncSession = Depends(get_session),
):
    current = await get_ai_runtime_config(force_refresh=True)
    base_url = data.base_url.strip().rstrip("/")
    model = data.model.strip()
    api_key = current.api_key if data.api_key is None else data.api_key.strip()
    if base_url and not base_url.startswith(("http://", "https://")):
        raise HTTPException(422, detail="AI_BASE_URL_INVALID")
    if settings.is_production() and base_url and not base_url.startswith("https://"):
        raise HTTPException(422, detail="AI_BASE_URL_HTTPS_REQUIRED")
    if data.enabled and not (api_key and base_url and model):
        raise HTTPException(422, detail="AI_PROVIDER_CONFIG_INCOMPLETE")
    if data.enabled and not settings.AI_POLITICAL_CLASSIFIER_URL.strip() and not data.moderation_provider_fallback_enabled:
        raise HTTPException(422, detail="AI_MODERATION_PATH_REQUIRED")

    config = AIRuntimeConfig(
        enabled=data.enabled,
        api_key=api_key,
        base_url=base_url,
        model=model,
        moderation_provider_fallback_enabled=data.moderation_provider_fallback_enabled,
        source="database",
    )
    row = (await session.execute(select(SiteSetting).where(SiteSetting.key == AI_PROVIDER_SETTING_KEY))).scalar_one_or_none()
    if row is None:
        row = SiteSetting(key=AI_PROVIDER_SETTING_KEY)
        session.add(row)
    row.value = serialize_database_config(config)
    await session.commit()
    invalidate_ai_runtime_config()
    return _admin_ai_settings_response(await get_ai_runtime_config(force_refresh=True))


@router.delete("/ai-settings", status_code=204)
async def reset_admin_ai_settings(
    _user: User = Depends(super_admin_required),
    session: AsyncSession = Depends(get_session),
) -> None:
    row = (await session.execute(select(SiteSetting).where(SiteSetting.key == AI_PROVIDER_SETTING_KEY))).scalar_one_or_none()
    if row is not None:
        await session.delete(row)
        await session.commit()
    invalidate_ai_runtime_config()


# ── Level Names ──

DEFAULT_LEVEL_NAMES = {level: f"Level {level}" for level in range(1, 6)}


def _normalize_level_names(value: object) -> dict[int, str] | None:
    """Validate persisted level names before they reach the UI."""
    if not isinstance(value, dict):
        return None
    if len(value) != 5 or {str(key) for key in value} != {"1", "2", "3", "4", "5"}:
        return None
    normalized: dict[int, str] = {}
    for key, label in value.items():
        if not isinstance(label, str):
            return None
        label = label.strip()
        if not label or len(label) > 80:
            return None
        normalized[int(key)] = label
    return normalized


@router.get("/level-names")
async def get_level_names(session: AsyncSession = Depends(get_session)):
    from app.db.models.settings import SiteSetting
    row = (await session.execute(select(SiteSetting).where(SiteSetting.key == "level_names"))).scalar_one_or_none()
    import json
    if row and row.value:
        try:
            normalized = _normalize_level_names(json.loads(row.value))
        except (TypeError, ValueError):
            normalized = None
        if normalized is not None:
            return normalized
    return DEFAULT_LEVEL_NAMES


@router.put("/level-names")
async def set_level_names(
    data: object = Body(...),
    user: User = Depends(super_admin_required),
    session: AsyncSession = Depends(get_session),
):
    from app.db.models.settings import SiteSetting
    import json
    normalized = _normalize_level_names(data)
    if normalized is None:
        raise HTTPException(422, detail="INVALID_LEVEL_NAMES")
    row = (await session.execute(select(SiteSetting).where(SiteSetting.key == "level_names"))).scalar_one_or_none()
    if not row:
        row = SiteSetting(key="level_names")
        session.add(row)
    row.value = json.dumps(normalized, ensure_ascii=False)
    await session.commit()
    return {"ok": True}
