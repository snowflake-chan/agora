from uuid import UUID

from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import check_not_banned
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
from app.users.deps import current_user
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
        level=g.level or calc_guild_level(mc),
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

    g = Guild(
        name=body.name,
        logo=body.logo,
        description=body.description,
        president_id=user.id,
    )
    session.add(g)
    await session.flush()

    m = GuildMember(guild_id=g.id, user_id=user.id, role="president")
    session.add(m)
    await session.commit()
    await session.refresh(g)
    return await _guild_to_read(g, session)


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
    g = (await session.execute(select(Guild).where(Guild.id == guild_id))).scalar_one_or_none()
    if not g:
        raise HTTPException(404, detail="GUILD_NOT_FOUND")
    if g.president_id != user.id:
        raise HTTPException(403, detail="GUILD_PRESIDENT_REQUIRED")
    if body.name is not None:
        g.name = body.name
    if "logo" in body.model_fields_set:
        g.logo = body.logo
    if "description" in body.model_fields_set:
        g.description = body.description
    if body.level is not None and user.role == "super_admin":
        g.level = body.level
    await session.commit()
    await session.refresh(g)
    return await _guild_to_read(g, session)


@router.delete("/{guild_id}")
async def delete_guild(
    guild_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
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
    g = (await session.execute(select(Guild).where(Guild.id == guild_id))).scalar_one_or_none()
    if not g:
        raise HTTPException(404, detail="GUILD_NOT_FOUND")
    await check_not_banned(user.id, session)
    existing = (await session.execute(
        select(GuildMember).where(GuildMember.guild_id == guild_id, GuildMember.user_id == user.id)
    )).scalar_one_or_none()
    if existing and existing.status != "rejected":
        code = "GUILD_REQUEST_PENDING" if existing.status == "pending" else "GUILD_ALREADY_MEMBER"
        raise HTTPException(409, detail=code)
    if existing and existing.status == "rejected":
        await session.delete(existing)
        await session.flush()
    m = GuildMember(guild_id=guild_id, user_id=user.id, role="member", status="pending")
    session.add(m)
    await session.commit()
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
    await _require_guild_admin(guild_id, user, session)
    m = (await session.execute(
        select(GuildMember).where(GuildMember.id == member_id, GuildMember.guild_id == guild_id)
    )).scalar_one_or_none()
    if not m or m.status != "pending":
        raise HTTPException(404)
    m.status = "approved"
    await session.commit()
    return {"ok": True}


@router.post("/{guild_id}/requests/{member_id}/reject")
async def reject_request(
    guild_id: UUID,
    member_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    await _require_guild_admin(guild_id, user, session)
    m = (await session.execute(
        select(GuildMember).where(GuildMember.id == member_id, GuildMember.guild_id == guild_id)
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
    g = (await session.execute(select(Guild).where(Guild.id == guild_id))).scalar_one_or_none()
    if not g or g.president_id != me.id:
        raise HTTPException(403, detail="GUILD_PRESIDENT_REQUIRED")
    if role not in ("vice_president", "member"):
        raise HTTPException(400)

    target = (await session.execute(
        select(GuildMember).where(GuildMember.guild_id == guild_id, GuildMember.user_id == user_id)
    )).scalar_one_or_none()
    if not target or target.status != "approved":
        raise HTTPException(404)
    if target.user_id == g.president_id:
        raise HTTPException(409, detail="GUILD_PRESIDENT_ROLE_LOCKED")

    if role == "vice_president":
        mc = (await session.execute(
            select(func.count(GuildMember.id)).where(GuildMember.guild_id == guild_id, GuildMember.status == "approved")
        )).scalar() or 0
        vp_count = (await session.execute(
            select(func.count(GuildMember.id)).where(
                GuildMember.guild_id == guild_id, GuildMember.role == "vice_president", GuildMember.status == "approved"
            )
        )).scalar() or 0
        max_vp = _MAX_VP.get(calc_guild_level(mc), 1)
        if vp_count >= max_vp:
            raise HTTPException(400, detail=f"MAX_VP_{max_vp}")

    target.role = role
    await session.commit()
    return {"ok": True}


@router.post("/{guild_id}/remove-member/{user_id}")
async def guild_remove_member(
    guild_id: UUID,
    user_id: UUID,
    me: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    actor = await _require_guild_admin(guild_id, me, session)
    target = (await session.execute(
        select(GuildMember).where(GuildMember.guild_id == guild_id, GuildMember.user_id == user_id)
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
    g = (await session.execute(select(Guild).where(Guild.id == guild_id))).scalar_one_or_none()
    if not g or g.president_id != me.id:
        raise HTTPException(403, detail="GUILD_PRESIDENT_REQUIRED")
    m = (await session.execute(
        select(GuildMember).where(GuildMember.guild_id == guild_id, GuildMember.user_id == user_id)
    )).scalar_one_or_none()
    if not m:
        raise HTTPException(404, detail="GUILD_MEMBERSHIP_NOT_FOUND")
    if m.user_id == g.president_id:
        raise HTTPException(409, detail="GUILD_PRESIDENT_ROLE_LOCKED")
    m.role = role
    await session.commit()
    await session.refresh(m)
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
    session: AsyncSession = Depends(get_session),
):
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
    stmt = (
        select(PatchModel)
        .where(PatchModel.author_id.in_(member_ids))
        .order_by(PatchModel.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    patches = (await session.execute(stmt)).scalars().all()

    patch_ids = [str(p.id) for p in patches]
    counts_map: dict = {}
    if patch_ids:
        rows = (await session.execute(
            select(VoteModel.patch_id, VoteModel.choice, func.count(VoteModel.id))
            .where(VoteModel.patch_id.in_(patch_ids))
            .group_by(VoteModel.patch_id, VoteModel.choice)
        )).all()
        for pid, choice, cnt in rows:
            key = str(pid)
            if key not in counts_map:
                counts_map[key] = {"for": 0, "against": 0, "abstain": 0}
            counts_map[key][choice] = cnt

    return [
        PatchRead(
            id=p.id, title=p.title, content=p.content,
            pr_number=p.pr_number, status=p.status,
            author_id=p.author_id,
            author_username=p.author.username if p.author else "",
            voting_ends_at=p.voting_ends_at,
            for_count=counts_map.get(str(p.id), {}).get("for", 0),
            against_count=counts_map.get(str(p.id), {}).get("against", 0),
            abstain_count=counts_map.get(str(p.id), {}).get("abstain", 0),
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
    member = (await session.execute(
        select(GuildMember).where(
            GuildMember.guild_id == guild_id, GuildMember.user_id == user.id
        )
    )).scalar_one_or_none()
    _guild_forbidden(member)

    rows = (
        await session.execute(
            select(ContentModel)
            .where(ContentModel.guild_id == guild_id, ContentModel.type == "guild_post")
            .order_by(ContentModel.created_at.desc())
        )
    ).scalars().all()

    return [
        GuildDiscussionRead(
            id=r.id, title=r.title, content=r.content,
            author_id=r.author_id,
            author_username=r.author.username if r.author else "",
            created_at=r.created_at,
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

    c = ContentModel(
        type="guild_post",
        title=body.title,
        content=body.content,
        author_id=user.id,
        guild_id=guild_id,
    )
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return GuildDiscussionRead(
        id=c.id, title=c.title, content=c.content,
        author_id=c.author_id,
        author_username=user.username,
        created_at=c.created_at,
    )


# ── Delete Discussion ──


@router.delete("/{guild_id}/discussions/{post_id}")
async def delete_discussion(
    guild_id: UUID,
    post_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
):
    c = (await session.execute(
        select(ContentModel).where(
            ContentModel.id == post_id,
            ContentModel.guild_id == guild_id,
            ContentModel.type == "guild_post",
        )
    )).scalar_one_or_none()
    if not c:
        raise HTTPException(404)
    if c.author_id != user.id:
        raise HTTPException(403, detail="GUILD_DISCUSSION_AUTHOR_REQUIRED")
    await session.delete(c)
    await session.commit()
    return {"ok": True}


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
        guild_level=calc_guild_level(mc),
        role=m.role,
    )
