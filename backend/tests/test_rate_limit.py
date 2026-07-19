"""Authentication rate-limit regression tests."""

from uuid import uuid4

import httpx
import pytest

from app.users import rate_limit

pytestmark = pytest.mark.usefixtures("server")

BASE = "http://localhost:8000/api/v1/auth"


def test_repeated_login_attempts_are_limited():
    email = f"missing-{uuid4().hex}@example.com"

    for _ in range(10):
        response = httpx.post(
            f"{BASE}/login",
            json={"email": email, "password": "wrong-password"},
        )
        assert response.status_code == 401

    blocked = httpx.post(
        f"{BASE}/login",
        json={"email": email, "password": "wrong-password"},
    )
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == "RATE_LIMIT_EXCEEDED"
    assert int(blocked.headers["retry-after"]) > 0


@pytest.mark.asyncio
async def test_rate_limit_fails_open_when_redis_is_unavailable(monkeypatch):
    async def unavailable():
        raise ConnectionError("Redis offline")

    monkeypatch.setattr(rate_limit, "get_redis", unavailable)

    await rate_limit.enforce_rate_limit(
        scope="login",
        identifier="user@example.com",
        limit=1,
        window_seconds=60,
    )


def test_rate_limit_keys_do_not_contain_identifiers():
    key = rate_limit._key("login", "private@example.com")

    assert "private@example.com" not in key
    assert key.startswith("rate_limit:login:")
