from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, func, select, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import lazyload

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import check_not_banned, require_content_visible
from app.content_moderation import (
    assess_content_moderation_after_read,
    content_visibility_clause,
    moderation_metadata_for,
    notify_content_pending,
)
from app.db import get_session
from app.db.models.content import Content as ContentModel
from app.db.models.guild import Guild, GuildMember
from app.db.models.patch import Patch as PatchModel
from app.db.models.user import User
from app.db.models.vote import Vote as VoteModel
from app.schemas.guild import (
    GuildCreate, GuildRead, GuildUpdate,
    GuildMemberRead, GuildDiscussionCreate, GuildDiscussionRead,
    UserGuildBadge,
)
from app.tokens import service as token_service
from app.users.deps import current_user, optional_current_user
from app.utils import calc_guild_level

router = APIRouter()


def _approved_membership():
    return or_(
        GuildMember.status == "approved",
        GuildMember.status.is_(None),
        GuildMember.status == "",
    )


async def _guild_to_read(g: Guild, session: AsyncSession) -> GuildRead:
    mc = (
        await session.execute(
            select(func.count(GuildMember.id)).where(
                GuildMember.guild_id == g.id,
                _approved_membership(),
            )
        )
    ).scalar() or 0
    return GuildRead(
        id=g.id,
        name=g.name,
        logo=g.logo,
        description=g.description,
        president_id=g.president_id,
        president_username=g.president.username if g.president else "",
        member_count=mc,
        level=g.level or calc_guild_level(g.proposal_score),
        created_at=g.created_at,
    )


# ── List / Create Guilds ──


@router.get("", response_model=list[GuildRead])
async def list_guilds(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Guild).order_by(Guild.created_at.desc()))).scalars().all()
    return [await _guild_to_read(g, session) for g in rows]


@router.post("", response_model=GuildRead)
async def create_guild(
    body: GuildCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await check_not_banned(user.id, session)
    # Serialise the per-user president check so concurrent requests cannot
    # create two studios for the same account.
    await session.scalar(select(User.id).where(User.id == user.id).with_for_update())
    existing = (await session.execute(
        select(Guild).where(Guild.president_id == user.id)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(409, detail="GUILD_PRESIDENT_ALREADY_EXISTS")
    duplicate_name = (await session.execute(
        select(Guild.id).where(Guild.name == body.name)
    )).scalar_one_or_none()
    if duplicate_name:
        raise HTTPException(409, detail="GUILD_NAME_TAKEN")

    # Token economy: charge one-time guild creation fee
    fee = await token_service.get_param(session, "guild_create_fee")
    try:
        await token_service.spend(session, user.id, fee, "guild_create")
    except ValueError:
        raise HTTPException(402, detail=f"INSUFFICIENT_AGC_NEED_{fee}")

    g = Guild(
        name=body.name,
        logo=body.logo,
        description=body.description,
        president_id=user.id,
    )
    session.add(g)
    try:
        # The unique guild name constraint can fail during flush, before
        # commit. Keep the entire write sequence inside the conflict handler.
        await session.flush()
        m = GuildMember(guild_id=g.id, user_id=user.id, role="president")
        session.add(m)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, detail="GUILD_NAME_TAKEN") from exc
    await session.refresh(g)
    return await _guild_to_read(g, session)


# ── User Guild Badge ──


@router.get("/-/my", response_model=UserGuildBadge | None)
async def my_guild(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    m = (await session.execute(
        select(GuildMember)
        .where(GuildMember.user_id == user.id, _approved_membership())
        .order_by(GuildMember.joined_at)
        .limit(1)
    )).scalars().first()
    if not m:
        return None
    mc = (await session.execute(
        select(func.count(GuildMember.id)).where(
            GuildMember.guild_id == m.guild_id,
            _approved_membership(),
        )
    )).scalar() or 0
    return UserGuildBadge(
        guild_id=m.guild_id,
        guild_name=m.guild.name,
        guild_level=m.guild.level or calc_guild_level(m.guild.proposal_score),
        role=m.role,
    )


# ── Single Guild ──


@router.get("/{guild_id}", response_model=GuildRead)
async def get_guild(guild_id: UUID, session: AsyncSession = Depends(get_session)):
    g = (await session.execute(select(Guild).where(Guild.id == guild_id))).scalar_one_or_none()
    if not g:
        raise HTTPException(404, detail="GUILD_NOT_FOUND")
    return await _guild_to_read(g, session)


@router.patch("/{guild_id}", response_model=GuildRead)
async def update_guild(
    guild_id: UUID,
    body: GuildUpdate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await check_not_banned(user.id, session)
    g = (await session.execute(select(Guild).where(Guild.id == guild_id))).scalar_one_or_none()
    if not g:
        raise HTTPException(404, detail="GUILD_NOT_FOUND")
    if g.president_id != user.id:
        raise HTTPException(403, detail="GUILD_PRESIDENT_REQUIRED")
    if body.name is not None:
        duplicate_name = await session.scalar(
            select(Guild.id).where(
                Guild.name == body.name,
                Guild.id != guild_id,
            )
        )
        if duplicate_name:
            raise HTTPException(409, detail="GUILD_NAME_TAKEN")
        g.name = body.name
    if "logo" in body.model_fields_set:
        g.logo = body.logo
    if "description" in body.model_fields_set:
        g.description = body.description
    if body.level is not None and user.role == "super_admin":
        g.level = body.level
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, detail="GUILD_NAME_TAKEN") from exc
    await session.refresh(g)
    return await _guild_to_read(g, session)


@router.delete("/{guild_id}")
async def delete_guild(
    guild_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await check_not_banned(user.id, session)
    g = (await session.execute(select(Guild).where(Guild.id == guild_id))).scalar_one_or_none()
    if not g:
        raise HTTPException(404)
    if g.president_id != user.id:
        raise HTTPException(403, detail="GUILD_PRESIDENT_REQUIRED")
    await session.delete(g)
    await session.commit()
    return {"ok": True}


# ── Join / Leave ──


@router.post("/{guild_id}/join")
async def join_guild(
    guild_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await check_not_banned(user.id, session)
    # Lock both sides of the membership invariant before reading it. This
    # turns concurrent join/retry requests into a stable 409 instead of a
    # uniqueness-constraint 500.
    await session.scalar(select(User.id).where(User.id == user.id).with_for_update())
    guild_exists = await session.scalar(
        select(Guild.id).where(Guild.id == guild_id).with_for_update()
    )
    if guild_exists is None:
        raise HTTPException(404, detail="GUILD_NOT_FOUND")
    existing = (await session.execute(
        select(GuildMember)
        .options(lazyload(GuildMember.guild), lazyload(GuildMember.user))
        .where(GuildMember.guild_id == guild_id, GuildMember.user_id == user.id)
        .with_for_update()
    )).scalar_one_or_none()
    if existing and existing.status != "rejected":
        code = "GUILD_REQUEST_PENDING" if existing.status == "pending" else "GUILD_ALREADY_MEMBER"
        raise HTTPException(409, detail=code)
    if existing and existing.status == "rejected":
        await session.delete(existing)
        await session.flush()
    m = GuildMember(guild_id=guild_id, user_id=user.id, role="member", status="pending")
    session.add(m)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, detail="GUILD_REQUEST_PENDING") from exc
    return {"ok": True, "status": "pending"}


@router.post("/{guild_id}/leave")
async def leave_guild(
    guild_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    m = (await session.execute(
        select(GuildMember).where(GuildMember.guild_id == guild_id, GuildMember.user_id == user.id)
    )).scalar_one_or_none()
    if not m:
        raise HTTPException(404, detail="GUILD_MEMBERSHIP_NOT_FOUND")
    if m.role == "president":
        raise HTTPException(409, detail="GUILD_PRESIDENT_CANNOT_LEAVE")
    await session.delete(m)
    await session.commit()
    return {"ok": True}


# ── Guild approval (president / vice_president) ──

async def _require_guild_admin(guild_id: UUID, user: User, session: AsyncSession):
    m = (await session.execute(
        select(GuildMember).where(
            GuildMember.guild_id == guild_id, GuildMember.user_id == user.id,
            _approved_membership(),
            GuildMember.role.in_(["president", "vice_president"])
        )
    )).scalar_one_or_none()
    if not m:
        raise HTTPException(403, detail="GUILD_ADMIN_REQUIRED")
    return m


async def _require_guild_admin_for_update(
    guild_id: UUID,
    user: User,
    session: AsyncSession,
) -> GuildMember:
    """Lock the guild and actor before authorizing a management mutation."""
    guild_exists = await session.scalar(
        select(Guild.id).where(Guild.id == guild_id).with_for_update()
    )
    if guild_exists is None:
        raise HTTPException(404, detail="GUILD_NOT_FOUND")
    actor = (
        await session.execute(
            select(GuildMember)
            .options(lazyload(GuildMember.guild), lazyload(GuildMember.user))
            .where(
                GuildMember.guild_id == guild_id,
                GuildMember.user_id == user.id,
                _approved_membership(),
                GuildMember.role.in_(["president", "vice_president"]),
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if actor is None:
        raise HTTPException(403, detail="GUILD_ADMIN_REQUIRED")
    return actor


async def _set_member_role(
    guild_id: UUID,
    user_id: UUID,
    role: str,
    president: User,
    session: AsyncSession,
) -> GuildMember:
    """Change a member role while serialising changes for one guild.

    The guild row is the lock for the role-cap invariant.  Keeping this in one
    helper prevents the legacy PATCH endpoint from bypassing the checks used by
    the dedicated promote endpoint.
    """
    guild_row = (
        await session.execute(
            select(Guild.id, Guild.president_id, Guild.level)
            .where(Guild.id == guild_id)
            .with_for_update()
        )
    ).one_or_none()
    if not guild_row or guild_row.president_id != president.id:
        raise HTTPException(403, detail="GUILD_PRESIDENT_REQUIRED")

    target = (
        await session.execute(
            select(GuildMember)
            .options(lazyload(GuildMember.guild), lazyload(GuildMember.user))
            .where(
                GuildMember.guild_id == guild_id,
                GuildMember.user_id == user_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not target or target.status not in (None, "", "approved"):
        raise HTTPException(404, detail="GUILD_MEMBERSHIP_NOT_FOUND")
    if target.user_id == guild_row.president_id:
        raise HTTPException(409, detail="GUILD_PRESIDENT_ROLE_LOCKED")

    if role == "vice_president" and target.role != "vice_president":
        member_count = (
            await session.execute(
                select(func.count(GuildMember.id)).where(
                    GuildMember.guild_id == guild_id,
                    _approved_membership(),
                )
            )
        ).scalar() or 0
        vp_count = (
            await session.execute(
                select(func.count(GuildMember.id)).where(
                    GuildMember.guild_id == guild_id,
                    GuildMember.role == "vice_president",
                    _approved_membership(),
                )
            )
        ).scalar() or 0
        guild_level = guild_row.level or calc_guild_level(guild_row.proposal_score)
        max_vp = _MAX_VP.get(guild_level, 1)
        if vp_count >= max_vp:
            raise HTTPException(409, detail="GUILD_VP_LIMIT_REACHED")

    target.role = role
    await session.commit()
    # The lock query deliberately disables joined relationships (PostgreSQL
    # cannot lock the nullable side of those joins). Re-fetch after commit so
    # response construction can safely use the eagerly-loaded user relation.
    return (
        await session.execute(
            select(GuildMember).where(GuildMember.id == target.id)
        )
    ).scalar_one()


@router.get("/{guild_id}/requests")
async def list_requests(
    guild_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await _require_guild_admin(guild_id, user, session)
    rows = (await session.execute(
        select(GuildMember).where(GuildMember.guild_id == guild_id, GuildMember.status == "pending")
    )).scalars().all()
    return [dict(id=m.id, user_id=m.user_id, username=m.user.username if m.user else "",
                 nickname=m.user.nickname if m.user else None, joined_at=m.joined_at.isoformat()) for m in rows]


@router.post("/{guild_id}/requests/{member_id}/approve")
async def approve_request(
    guild_id: UUID,
    member_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await check_not_banned(user.id, session)
    await _require_guild_admin_for_update(guild_id, user, session)
    m = (await session.execute(
        select(GuildMember)
        .options(lazyload(GuildMember.guild), lazyload(GuildMember.user))
        .where(GuildMember.id == member_id, GuildMember.guild_id == guild_id)
        .with_for_update()
    )).scalar_one_or_none()
    if not m or m.status != "pending":
        raise HTTPException(404)
    m.role = "member"
    m.status = "approved"

    # Guild leveling: lock the new member's uncounted passed proposals
    from app.guilds.leveling import lock_user_proposals
    await lock_user_proposals(session, guild_id, m.user_id)

    await session.commit()
    return {"ok": True}


@router.post("/{guild_id}/requests/{member_id}/reject")
async def reject_request(
    guild_id: UUID,
    member_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await check_not_banned(user.id, session)
    await _require_guild_admin_for_update(guild_id, user, session)
    m = (await session.execute(
        select(GuildMember)
        .options(lazyload(GuildMember.guild), lazyload(GuildMember.user))
        .where(GuildMember.id == member_id, GuildMember.guild_id == guild_id)
        .with_for_update()
    )).scalar_one_or_none()
    if not m or m.status != "pending":
        raise HTTPException(404)
    m.status = "rejected"
    await session.commit()
    return {"ok": True}


# ── Guild vice-presidents by level ──

_MAX_VP = {1: 1, 2: 1, 3: 2, 4: 3, 5: 4}


@router.post("/{guild_id}/promote/{user_id}")
async def promote_member(
    guild_id: UUID,
    user_id: UUID,
    role: str = Query("vice_president"),
    me: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await check_not_banned(me.id, session)
    if role not in ("vice_president", "member"):
        raise HTTPException(400)
    await _set_member_role(guild_id, user_id, role, me, session)
    return {"ok": True}


@router.post("/{guild_id}/remove-member/{user_id}")
async def guild_remove_member(
    guild_id: UUID,
    user_id: UUID,
    me: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await check_not_banned(me.id, session)
    actor = await _require_guild_admin_for_update(guild_id, me, session)
    target = (await session.execute(
        select(GuildMember)
        .options(lazyload(GuildMember.guild), lazyload(GuildMember.user))
        .where(GuildMember.guild_id == guild_id, GuildMember.user_id == user_id)
        .with_for_update()
    )).scalar_one_or_none()
    if not target:
        raise HTTPException(404)
    if target.role == "president":
        raise HTTPException(409, detail="GUILD_PRESIDENT_ROLE_LOCKED")
    if actor.role != "president" and target.role != "member":
        raise HTTPException(403, detail="GUILD_PRESIDENT_REQUIRED")
    await session.delete(target)
    await session.commit()
    return {"ok": True}


# ── Members ──


@router.get("/{guild_id}/members", response_model=list[GuildMemberRead])
async def list_members(guild_id: UUID, session: AsyncSession = Depends(get_session)):
    rows = (
        await session.execute(
            select(GuildMember).where(
                GuildMember.guild_id == guild_id,
                _approved_membership(),
            ).order_by(GuildMember.joined_at)
        )
    ).scalars().all()
    return [
        GuildMemberRead(
            id=m.id,
            user_id=m.user_id,
            username=m.user.username if m.user else "",
            nickname=m.user.nickname if m.user else None,
            role=m.role,
            status=m.status or "approved",
            joined_at=m.joined_at,
        )
        for m in rows
    ]


@router.get("/{guild_id}/membership", response_model=GuildMemberRead | None)
async def get_my_membership(
    guild_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    member = (await session.execute(
        select(GuildMember).where(
            GuildMember.guild_id == guild_id,
            GuildMember.user_id == user.id,
        )
    )).scalar_one_or_none()
    if not member:
        return None
    return GuildMemberRead(
        id=member.id,
        user_id=member.user_id,
        username=member.user.username if member.user else "",
        nickname=member.user.nickname if member.user else None,
        role=member.role,
        status=member.status or "approved",
        joined_at=member.joined_at,
    )


@router.patch("/{guild_id}/members/{user_id}", response_model=GuildMemberRead)
async def update_member_role(
    guild_id: UUID,
    user_id: UUID,
    role: str = Query(...),
    me: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    if role not in ("vice_president", "member"):
        raise HTTPException(400, detail="INVALID_GUILD_ROLE")
    await check_not_banned(me.id, session)
    m = await _set_member_role(guild_id, user_id, role, me, session)
    return GuildMemberRead(
        id=m.id, user_id=m.user_id,
        username=m.user.username if m.user else "",
        nickname=m.user.nickname if m.user else None,
        role=m.role, status=m.status or "approved", joined_at=m.joined_at,
    )


# ── Guild Patches ──


@router.get("/{guild_id}/patches")
async def list_guild_patches(
    guild_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User | None = Depends(optional_current_user),
    session: AsyncSession = Depends(get_session),
):
    guild_exists = await session.scalar(select(Guild.id).where(Guild.id == guild_id))
    if guild_exists is None:
        raise HTTPException(404, detail="GUILD_NOT_FOUND")

    # Get member user IDs
    member_ids = (await session.execute(
        select(GuildMember.user_id).where(
            GuildMember.guild_id == guild_id,
            _approved_membership(),
        )
    )).scalars().all()

    if not member_ids:
        return []

    from app.schemas.patch import PatchRead

    offset = (page - 1) * page_size
    visible_statuses = ("voting", "passed", "merged", "rejected", "failed")
    visibility = PatchModel.status.in_(visible_statuses)
    if user is not None:
        # A draft remains available to its author while it is still associated
        # with an approved member of this guild; drafts are never public.
        visibility = or_(
            visibility,
            and_(PatchModel.status == "draft", PatchModel.author_id == user.id),
        )

    stmt = (
        select(PatchModel)
        .where(PatchModel.author_id.in_(member_ids), visibility)
        .order_by(PatchModel.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    patches = (await session.execute(stmt)).scalars().all()

    patch_ids = [p.id for p in patches]
    counts_map: dict = {}
    comment_counts: dict = {}
    if patch_ids:
        rows = (await session.execute(
            select(VoteModel.patch_id, VoteModel.choice, func.sum(VoteModel.weight))
            .where(VoteModel.patch_id.in_(patch_ids))
            .group_by(VoteModel.patch_id, VoteModel.choice)
        )).all()
        for pid, choice, cnt in rows:
            key = str(pid)
            if key not in counts_map:
                counts_map[key] = {"for": 0.0, "against": 0.0, "abstain": 0.0}
            counts_map[key][choice] = cnt
        comment_counts = dict(
            (
                await session.execute(
                    select(ContentModel.patch_id, func.count(ContentModel.id)).where(
                        ContentModel.patch_id.in_(patch_ids),
                        ContentModel.type == "comment",
                        content_visibility_clause(user),
                    ).group_by(ContentModel.patch_id)
                )
            ).all()
        )

    return [
        PatchRead(
            id=p.id, title=p.title, content=p.content,
            pr_number=p.pr_number, status=p.status,
            author_id=p.author_id,
            author_username=p.author.username if p.author else "",
            voting_started_at=p.voting_started_at,
            voting_ends_at=p.voting_ends_at,
            voting_period_hours=p.voting_period_hours,
            voting_window_kind=p.voting_window_kind,
            for_count=counts_map.get(str(p.id), {}).get("for", 0.0),
            against_count=counts_map.get(str(p.id), {}).get("against", 0.0),
            abstain_count=counts_map.get(str(p.id), {}).get("abstain", 0.0),
            comment_count=comment_counts.get(p.id, 0),
            revision_number=p.revision_number,
            created_at=p.created_at, updated_at=p.updated_at,
        )
        for p in patches
    ]


# ── Guild Discussions ──


def _guild_forbidden(member):
    if not member or member.status not in (None, "", "approved"):
        raise HTTPException(403, detail="GUILD_MEMBERSHIP_REQUIRED")


@router.get("/{guild_id}/discussions", response_model=list[GuildDiscussionRead])
async def list_discussions(
    guild_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    allow_staff = user.role in ("moderator", "super_admin")
    if user.role not in ("moderator", "super_admin"):
        member = (await session.execute(
            select(GuildMember).where(
                GuildMember.guild_id == guild_id, GuildMember.user_id == user.id
            )
        )).scalar_one_or_none()
        _guild_forbidden(member)

    rows = (
        await session.execute(
            select(ContentModel)
            .where(
                ContentModel.guild_id == guild_id,
                ContentModel.type == "guild_post",
                content_visibility_clause(user, allow_staff=allow_staff),
            )
            .order_by(ContentModel.created_at.desc())
        )
    ).scalars().all()

    return [
        GuildDiscussionRead(
            id=r.id, title=r.title, content=r.content,
            author_id=r.author_id,
            author_username=r.author.username if r.author else "",
            **moderation_metadata_for(r, user, allow_staff=allow_staff),
            revision_number=r.revision_number,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


@router.post("/{guild_id}/discussions", response_model=GuildDiscussionRead)
async def create_discussion(
    guild_id: UUID,
    body: GuildDiscussionCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    member = (await session.execute(
        select(GuildMember).where(
            GuildMember.guild_id == guild_id, GuildMember.user_id == user.id
        )
    )).scalar_one_or_none()
    _guild_forbidden(member)
    await check_not_banned(user.id, session, "mute_post")

    moderation = await assess_content_moderation_after_read(
        session,
        body.title or "",
        body.content,
    )

    # Membership can change while semantic review is in flight. Lock and
    # recheck it, plus posting restrictions, in the write transaction.
    member = (
        await session.execute(
            select(GuildMember.id, GuildMember.status)
            .where(
                GuildMember.guild_id == guild_id,
                GuildMember.user_id == user.id,
            )
            .with_for_update()
        )
    ).one_or_none()
    _guild_forbidden(member)
    await check_not_banned(user.id, session, "mute_post")

    c = ContentModel(
        type="guild_post",
        title=body.title,
        content=body.content,
        author_id=user.id,
        guild_id=guild_id,
        moderation_status=moderation.status,
        moderation_reason=moderation.reason,
        published_at=(
            datetime.now(timezone.utc)
            if moderation.status == "published"
            else None
        ),
    )
    session.add(c)
    await session.commit()
    await session.refresh(c)
    if c.moderation_status == "pending_review":
        await notify_content_pending(c)
    return GuildDiscussionRead(
        id=c.id, title=c.title, content=c.content,
        author_id=c.author_id,
        author_username=user.username,
        **moderation_metadata_for(c, user),
        revision_number=c.revision_number,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


# ── Delete Discussion ──


@router.delete("/{guild_id}/discussions/{post_id}")
async def delete_discussion(
    guild_id: UUID,
    post_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
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
    await require_content_visible(c, user, session)
    if c.author_id != user.id:
        raise HTTPException(403, detail="GUILD_DISCUSSION_AUTHOR_REQUIRED")
    if c.revision_number > 1:
        raise HTTPException(409, detail="AUDITED_CONTENT_DELETE_LOCKED")
    await session.delete(c)
    await session.commit()
    return {"ok": True}


# ── Guild Proposal Contributions & Leveling ──


@router.get("/{guild_id}/proposals")
async def guild_proposals(
    guild_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    from app.guilds.leveling import guild_proposal_contributions
    items, total = await guild_proposal_contributions(session, guild_id, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{guild_id}/level")
async def guild_level_detail(
    guild_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    guild = await session.get(Guild, guild_id)
    if not guild:
        raise HTTPException(404, detail="GUILD_NOT_FOUND")

    score = guild.proposal_score
    current_level = guild.level or calc_guild_level(score)

    thresholds = {2: 5, 3: 15, 4: 30, 5: 50}
    next_level = None
    next_threshold = None
    for lv in range(current_level + 1, 6):
        if lv in thresholds:
            next_level = lv
            next_threshold = thresholds[lv]
            break

    return {
        "guild_id": str(guild_id),
        "proposal_score": score,
        "current_level": current_level,
        "next_level": next_level,
        "next_threshold": next_threshold,
        "progress_to_next": score / next_threshold if next_threshold else None,
    }
