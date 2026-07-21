from collections.abc import AsyncGenerator
from typing import Any

from fastapi import Depends
from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyAccessTokenDatabase
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.db.models.auth_session import AuthSession
from app.db.models.user import User


class LimitedAccessTokenDatabase(SQLAlchemyAccessTokenDatabase[AuthSession]):
    async def create(self, create_dict: dict[str, Any]) -> AuthSession:
        user_id = create_dict["user_id"]
        await self.session.execute(
            select(User.id).where(User.id == user_id).with_for_update()
        )
        existing_sessions = list(
            (
                await self.session.execute(
                    select(AuthSession)
                    .where(AuthSession.user_id == user_id)
                    .order_by(AuthSession.created_at.asc(), AuthSession.token.asc())
                )
            )
            .scalars()
            .all()
        )
        keep_existing = max(settings.AUTH_MAX_SESSIONS_PER_USER - 1, 0)
        remove_count = max(len(existing_sessions) - keep_existing, 0)
        for session in existing_sessions[:remove_count]:
            await self.session.delete(session)

        access_token = AuthSession(**create_dict)
        self.session.add(access_token)
        await self.session.commit()
        await self.session.refresh(access_token)
        return access_token


async def get_access_token_db(
    session: AsyncSession = Depends(get_session),
) -> AsyncGenerator[LimitedAccessTokenDatabase, None]:
    yield LimitedAccessTokenDatabase(session, AuthSession)
