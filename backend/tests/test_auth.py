"""Authentication transport security integration tests."""

from uuid import uuid4

import httpx
import pytest

pytestmark = pytest.mark.usefixtures("server")

BASE = "http://localhost:8000/api/v1/auth"


def _credentials() -> dict[str, str]:
    suffix = uuid4().hex[:10]
    return {
        "email": f"cookie-{suffix}@example.com",
        "username": f"cookie-{suffix}",
        "password": "testpass123",
    }


def _assert_secure_cookie(response: httpx.Response) -> None:
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("Authorization=")
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie


def test_register_sets_transport_cookie_policy():
    response = httpx.post(f"{BASE}/register", json=_credentials())

    assert response.status_code == 200
    _assert_secure_cookie(response)


def test_login_sets_transport_cookie_policy():
    credentials = _credentials()
    register = httpx.post(f"{BASE}/register", json=credentials)
    assert register.status_code == 200

    response = httpx.post(
        f"{BASE}/login",
        json={
            "email": credentials["email"],
            "password": credentials["password"],
        },
    )

    assert response.status_code == 200
    _assert_secure_cookie(response)


def test_logout_expires_cookie_with_same_policy():
    response = httpx.post(f"{BASE}/logout")

    assert response.status_code == 204
    _assert_secure_cookie(response)
    assert "Max-Age=0" in response.headers["set-cookie"]
