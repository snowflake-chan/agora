"""Shared dependencies for enforcement checks."""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.moderation import BanRecord


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
        expire_str = ban.expires_at.strftime("%Y-%m-%d %H:%M") if ban.expires_at else "永久"
        msg = {
            "ban_user": f"你的账号已被封禁至 {expire_str}",
            "mute_post": f"你已被禁止发帖至 {expire_str}",
            "mute_patch": f"你已被禁止发起变更至 {expire_str}",
        }.get(ban.type, f"你的账号已被限制至 {expire_str}")
        raise HTTPException(403, detail=msg)
