from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.config import settings
from app.db.models.auth_session import AuthSession
from app.users.sessions import LimitedAccessTokenDatabase


@pytest.mark.asyncio
async def test_new_session_prunes_oldest_tokens(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_MAX_SESSIONS_PER_USER", 3)
    now = datetime.now(timezone.utc)
    existing = [
        SimpleNamespace(token=f"token-{index}", created_at=now + timedelta(seconds=index))
        for index in range(4)
    ]
    scalar_result = Mock()
    scalar_result.scalars.return_value.all.return_value = existing
    session = AsyncMock()
    session.add = Mock()
    session.execute.side_effect = [Mock(), scalar_result]
    database = LimitedAccessTokenDatabase(session, AuthSession)
    user_id = uuid4()

    created = await database.create({"token": "new-token", "user_id": user_id})

    assert created.token == "new-token"
    assert created.user_id == user_id
    assert [call.args[0] for call in session.delete.await_args_list] == existing[:2]
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(created)


def test_user_manager_accepts_database_uuid_values():
    from app.users.manager import UserManager

    value = uuid4()

    assert UserManager.parse_id(None, value) == value
    assert UserManager.parse_id(None, str(value)) == value
