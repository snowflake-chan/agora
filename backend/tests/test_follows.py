"""Integration tests for follows and secondary activity notifications."""

from uuid import uuid4

import httpx
import pytest

BASE = "http://localhost:8000"

pytestmark = pytest.mark.usefixtures("server")


def _account(prefix: str) -> tuple[httpx.Client, dict]:
    client = httpx.Client()
    uid = uuid4().hex[:8]
    email = f"{prefix}-{uid}@test.dev"
    password = "testpass123"
    response = client.post(
        f"{BASE}/api/v1/auth/register",
        json={
            "email": email,
            "username": f"{prefix}-{uid}",
            "password": password,
        },
    )
    assert response.status_code == 200, response.text
    user = response.json()
    login = client.post(
        f"{BASE}/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text
    token = login.cookies.get("Authorization")
    assert token
    client.headers["Cookie"] = f"Authorization={token}"
    return client, user


def test_followed_author_posts_create_secondary_notification():
    follower, follower_user = _account("follower")
    author, author_user = _account("author")
    try:
        followed = follower.put(
            f"{BASE}/api/v1/users/{author_user['id']}/follow"
        )
        assert followed.status_code == 200
        assert followed.json()["is_following"] is True

        post = author.post(
            f"{BASE}/api/v1/posts",
            json={"title": "Followed post", "content": "New activity"},
        )
        assert post.status_code == 201, post.text
        post_id = post.json()["id"]

        notifications = follower.get(
            f"{BASE}/api/v1/notifications"
        ).json()["items"]
        assert any(
            item["type"] == "following_post"
            and item["link"] == f"/posts/{post_id}"
            for item in notifications
        )

        reply = follower.post(
            f"{BASE}/api/v1/posts/{post_id}/comments",
            json={"content": "Public reply"},
        )
        assert reply.status_code == 201
        reply_id = reply.json()["id"]

        own_content = follower.get(
            f"{BASE}/api/v1/users/{follower_user['id']}/content"
        ).json()
        item = next(content for content in own_content if content["id"] == reply_id)
        assert item["type"] == "comment"
        assert item["root_id"] == post_id
        assert item["root_title"] == "Followed post"
        assert item["can_delete"] is True
    finally:
        follower.close()
        author.close()


def test_cannot_follow_self():
    client, user = _account("self")
    try:
        response = client.put(f"{BASE}/api/v1/users/{user['id']}/follow")
        assert response.status_code == 422
    finally:
        client.close()
