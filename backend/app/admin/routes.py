from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import settings
from app.deps import check_not_banned
from app.db import get_session
from app.db.models.content import Content as ContentModel
from app.db.models.guild import Guild, GuildMember
from app.db.models.moderation import BanRecord, Report
from app.db.models.patch import Patch as PatchModel
from app.db.models.user import User
from app.db.models.vote import Vote as VoteModel
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


# ═══════════════════════════════════════════
#  Reports
# ═══════════════════════════════════════════


@router.post("/reports")
async def create_report(
    content_id: UUID | None = None,
    patch_id: UUID | None = None,
    reason: str = Query(..., min_length=1, max_length=500),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await check_not_banned(user.id, session)
    if content_id is None and patch_id is None:
        raise HTTPException(422, detail="REPORT_TARGET_REQUIRED")
    if content_id is not None and patch_id is not None:
        raise HTTPException(422, detail="REPORT_TARGET_AMBIGUOUS")

    normalized_reason = reason.strip()
    if not normalized_reason:
        raise HTTPException(422, detail="REPORT_REASON_REQUIRED")

    if content_id is not None:
        target_exists = await session.scalar(
            select(ContentModel.id)
            .where(ContentModel.id == content_id)
            .with_for_update()
        )
        target_filter = Report.content_id == content_id
        not_found_code = "CONTENT_NOT_FOUND"
    else:
        target_exists = await session.scalar(
            select(PatchModel.id)
            .where(PatchModel.id == patch_id)
            .with_for_update()
        )
        target_filter = Report.patch_id == patch_id
        not_found_code = "PATCH_NOT_FOUND"

    if target_exists is None:
        raise HTTPException(404, detail=not_found_code)

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
        if report.content_id is not None:
            target_type = "content"
            target_id = report.content_id
            target = report.content
            title = target.title if target else "(内容已删除)"
            body = target.content[:200] if target and target.content else ""
            author = target.author if target else None
        elif report.patch_id is not None:
            target_type = "patch"
            target_id = report.patch_id
            target = report.patch
            title = target.title if target else "(变更提案已删除)"
            body = target.content[:200] if target and target.content else ""
            author = target.author if target else None
        else:
            target_type = "deleted"
            target_id = None
            title = "(目标已删除)"
            body = ""
            author = None

        response.append(dict(
            id=report.id,
            target_type=target_type,
            target_id=target_id,
            content_id=report.content_id,
            patch_id=report.patch_id,
            content_title=title,
            content_body=body,
            content_author=author.username if author else "(已删除)",
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

    r = (await session.execute(select(Report).where(Report.id == report_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(404, detail="REPORT_NOT_FOUND")
    if r.content_id is not None and r.patch_id is not None:
        raise HTTPException(409, detail="REPORT_TARGET_INVALID")
    if action == "delete_post" and r.patch_id is not None:
        raise HTTPException(400, detail="INVALID_REPORT_ACTION")
    if action == "delete_patch" and r.content_id is not None:
        raise HTTPException(400, detail="INVALID_REPORT_ACTION")

    content_id = r.content_id
    patch_id = r.patch_id
    r.status = "dismissed" if action == "dismissed" else "resolved"

    others = []
    if content_id is not None or patch_id is not None:
        target_filter = (
            Report.content_id == content_id
            if content_id is not None
            else Report.patch_id == patch_id
        )
        others = (await session.execute(
            select(Report).where(
                target_filter,
                Report.status == "pending",
                Report.id != r.id,
            )
        )).scalars().all()
        for other in others:
            other.status = "resolved"

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
    return {"ok": True, "also_resolved": len(others)}


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
    c = (await session.execute(select(ContentModel).where(ContentModel.id == post_id))).scalar_one_or_none()
    if not c: raise HTTPException(404)
    await session.delete(c); await session.commit()
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
async def admin_update_guild(guild_id: UUID, name: str | None = Query(None, min_length=1, max_length=80), logo: str | None = Query(None, max_length=500), description: str | None = Query(None, max_length=2000), level: int | None = Query(None, ge=1, le=5), user: User = Depends(super_admin_required), session: AsyncSession = Depends(get_session)):
    g = (await session.execute(select(Guild).where(Guild.id == guild_id))).scalar_one_or_none()
    if not g: raise HTTPException(404)
    if name: g.name = name
    if logo is not None: g.logo = logo
    if description is not None: g.description = description
    if level is not None: g.level = level
    await session.commit()
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
    c = (await session.execute(select(ContentModel).where(ContentModel.id == post_id, ContentModel.guild_id == guild_id))).scalar_one_or_none()
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


# ── Level Names ──

DEFAULT_LEVEL_NAMES = {1: "heiker", 2: "black客", 3: "黑色的客人", 4: "黑客", 5: "Natriumchlorid"}


@router.get("/level-names")
async def get_level_names(session: AsyncSession = Depends(get_session)):
    from app.db.models.settings import SiteSetting
    row = (await session.execute(select(SiteSetting).where(SiteSetting.key == "level_names"))).scalar_one_or_none()
    import json
    if row and row.value:
        return json.loads(row.value)
    return DEFAULT_LEVEL_NAMES


@router.put("/level-names")
async def set_level_names(
    data: dict = None,
    user: User = Depends(super_admin_required),
    session: AsyncSession = Depends(get_session),
):
    from app.db.models.settings import SiteSetting
    import json
    row = (await session.execute(select(SiteSetting).where(SiteSetting.key == "level_names"))).scalar_one_or_none()
    if not row:
        row = SiteSetting(key="level_names")
        session.add(row)
    row.value = json.dumps(data, ensure_ascii=False)
    await session.commit()
    return {"ok": True}
