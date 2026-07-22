"""Authentication transport security integration tests."""

from uuid import uuid4

import httpx
import pytest

from app.config import settings

pytestmark = pytest.mark.usefixtures("server")

BASE = "http://localhost:8000/api/v1/auth"


def _credentials() -> dict[str, str]:
    suffix = uuid4().hex[:10]
    return {
        "email": f"cookie-{suffix}@example.com",
        "username": f"cookie-{suffix}",
        "password": "testpass123",
    }


def _assert_cookie_policy(response: httpx.Response) -> None:
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("Authorization=")
    assert "HttpOnly" in cookie
    assert ("Secure" in cookie) is settings.is_production()
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie


def test_register_sets_transport_cookie_policy():
    response = httpx.post(f"{BASE}/register", json=_credentials())

    assert response.status_code == 200
    _assert_cookie_policy(response)


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
    _assert_cookie_policy(response)


def test_logout_expires_cookie_with_same_policy():
    response = httpx.post(f"{BASE}/logout")

    assert response.status_code == 204
    _assert_cookie_policy(response)
    assert "Max-Age=0" in response.headers["set-cookie"]


def test_fourth_session_evicts_the_oldest_device():
    credentials = _credentials()
    registered = httpx.post(f"{BASE}/register", json=credentials)
    assert registered.status_code == 200
    tokens = [registered.cookies["Authorization"]]

    for _ in range(3):
        response = httpx.post(
            f"{BASE}/login",
            json={
                "email": credentials["email"],
                "password": credentials["password"],
            },
        )
        assert response.status_code == 200
        tokens.append(response.cookies["Authorization"])

    statuses = [
        httpx.get(
            "http://localhost:8000/api/v1/users/me",
            headers={"Cookie": f"Authorization={token}"},
        ).status_code
        for token in tokens
    ]

    assert statuses == [401, 200, 200, 200]


def test_logout_revokes_the_current_device_session():
    registered = httpx.post(f"{BASE}/register", json=_credentials())
    assert registered.status_code == 200
    token = registered.cookies["Authorization"]
    headers = {"Cookie": f"Authorization={token}"}

    logged_out = httpx.post(f"{BASE}/logout", headers=headers)

    assert logged_out.status_code == 204
    assert httpx.get(
        "http://localhost:8000/api/v1/users/me",
        headers=headers,
    ).status_code == 401
