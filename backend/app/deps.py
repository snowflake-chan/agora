"""Shared dependencies for enforcement checks."""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import lazyload

from app.db.models.content import Content as ContentModel
from app.db.models.guild import GuildMember
from app.db.models.moderation import BanRecord
from app.db.models.patch import Patch as PatchModel
from app.db.models.user import User


async def check_not_banned(user_id, session: AsyncSession, action: str = "ban_user"):
    """Raise 403 if user has an active ban/mute record matching `action`.

    action: "ban_user" (global) | "mute_post" | "mute_patch"
    """
    now = datetime.now(timezone.utc)
    ban = (
        await session.execute(
            select(BanRecord).where(
                BanRecord.target_user_id == user_id,
                BanRecord.is_active == True,
                or_(
                    BanRecord.type == "ban_user",  # global ban always checked
                    BanRecord.type == action,
                ),
                or_(BanRecord.expires_at.is_(None), BanRecord.expires_at > now),
            )
        )
    ).scalars().first()
    if ban:
        code = {
            "ban_user": "ACCOUNT_BANNED",
            "mute_post": "POSTING_RESTRICTED",
            "mute_patch": "PATCHING_RESTRICTED",
        }.get(ban.type, "ACCOUNT_RESTRICTED")
        raise HTTPException(403, detail=code)


def require_patch_visible(
    patch: PatchModel | None,
    user: User | None,
    *,
    allow_staff: bool = False,
) -> PatchModel:
    """Hide drafts except from their author or an explicitly allowed reviewer."""
    staff_can_review = bool(
        allow_staff and user and user.role in ("moderator", "super_admin")
    )
    if patch is None or (
        patch.status == "draft"
        and (user is None or (patch.author_id != user.id and not staff_can_review))
    ):
        raise HTTPException(status_code=404, detail="PATCH_NOT_FOUND")
    return patch


async def require_content_visible(
    content: ContentModel | None,
    user: User | None,
    session: AsyncSession,
    *,
    allow_staff: bool = False,
) -> ContentModel:
    """Enforce the privacy inherited by draft and guild-scoped content."""
    if content is None:
        raise HTTPException(status_code=404, detail="CONTENT_NOT_FOUND")

    if content.patch_id is not None:
        patch = await session.scalar(
            select(PatchModel)
            .options(lazyload(PatchModel.author))
            .where(PatchModel.id == content.patch_id)
        )
        require_patch_visible(patch, user, allow_staff=allow_staff)

    if content.guild_id is not None:
        if user is None:
            raise HTTPException(status_code=404, detail="CONTENT_NOT_FOUND")
        if user.role not in ("moderator", "super_admin"):
            membership = await session.scalar(
                select(GuildMember.id).where(
                    GuildMember.guild_id == content.guild_id,
                    GuildMember.user_id == user.id,
                    or_(
                        GuildMember.status == "approved",
                        GuildMember.status.is_(None),
                        GuildMember.status == "",
                    ),
                )
            )
            if membership is None:
                raise HTTPException(status_code=404, detail="CONTENT_NOT_FOUND")

    return content
