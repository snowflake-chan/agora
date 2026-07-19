"""Integration tests for post likes."""

from uuid import uuid4

import httpx


BASE = "http://localhost:8000"


def _register_and_login(client: httpx.Client) -> dict[str, str]:
    uid = uuid4().hex[:8]
    email = f"like-{uid}@test.dev"
    password = "testpass123"
    register = client.post(
        f"{BASE}/api/v1/auth/register",
        json={"email": email, "username": f"like-{uid}", "password": password},
    )
    assert register.status_code == 200, register.text
    login = client.post(
        f"{BASE}/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text
    cookie = login.cookies.get("Authorization")
    return {"Cookie": f"Authorization={cookie}"}


def _create_post(client: httpx.Client, headers: dict[str, str]) -> str:
    response = client.post(
        f"{BASE}/api/v1/posts",
        json={"title": "Like me", "content": "A reaction test"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_like_and_unlike_are_idempotent():
    with httpx.Client() as client:
        headers = _register_and_login(client)
        post_id = _create_post(client, headers)

        first = client.put(f"{BASE}/api/v1/posts/{post_id}/like", headers=headers)
        second = client.put(f"{BASE}/api/v1/posts/{post_id}/like", headers=headers)
        assert first.status_code == second.status_code == 200
        assert second.json() == {"like_count": 1, "liked_by_me": True}

        detail = client.get(f"{BASE}/api/v1/posts/{post_id}", headers=headers)
        assert detail.json()["like_count"] == 1
        assert detail.json()["liked_by_me"] is True

        first_remove = client.delete(
            f"{BASE}/api/v1/posts/{post_id}/like", headers=headers
        )
        second_remove = client.delete(
            f"{BASE}/api/v1/posts/{post_id}/like", headers=headers
        )
        assert first_remove.status_code == second_remove.status_code == 200
        assert second_remove.json() == {"like_count": 0, "liked_by_me": False}


def test_like_requires_auth_and_a_real_post():
    with httpx.Client() as client:
        headers = _register_and_login(client)
        post_id = _create_post(client, headers)

        unauthenticated = client.put(f"{BASE}/api/v1/posts/{post_id}/like")
        missing = client.put(
            f"{BASE}/api/v1/posts/{uuid4()}/like", headers=headers
        )
        assert unauthenticated.status_code == 401
        assert missing.status_code == 404
