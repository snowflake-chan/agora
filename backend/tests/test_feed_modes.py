"""Integration coverage for recommended, following, and latest feeds."""

from uuid import uuid4

import httpx


BASE = "http://localhost:8000"


def _account(prefix: str) -> tuple[httpx.Client, dict]:
    client = httpx.Client()
    uid = uuid4().hex[:8]
    email = f"{prefix}-{uid}@test.dev"
    password = "testpass123"
    registered = client.post(
        f"{BASE}/api/v1/auth/register",
        json={
            "email": email,
            "username": f"{prefix}-{uid}",
            "password": password,
        },
    )
    assert registered.status_code == 200, registered.text
    logged_in = client.post(
        f"{BASE}/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert logged_in.status_code == 200, logged_in.text
    token = logged_in.cookies.get("Authorization")
    assert token
    client.headers["Cookie"] = f"Authorization={token}"
    return client, registered.json()


def test_feed_modes_apply_relationships_and_ordering():
    follower, _ = _account("feed-follower")
    author, author_user = _account("feed-author")
    other, _ = _account("feed-other")
    try:
        followed = follower.put(
            f"{BASE}/api/v1/users/{author_user['id']}/follow"
        )
        assert followed.status_code == 200

        followed_post = author.post(
            f"{BASE}/api/v1/posts",
            json={
                "title": "Followed feed item",
                "content": "Relationship signal",
                "tags": ["ranking"],
            },
        )
        assert followed_post.status_code == 201, followed_post.text
        followed_id = followed_post.json()["id"]

        other_post = other.post(
            f"{BASE}/api/v1/posts",
            json={
                "title": "Latest feed item",
                "content": "Chronological signal",
            },
        )
        assert other_post.status_code == 201, other_post.text
        other_id = other_post.json()["id"]

        following = follower.get(
            f"{BASE}/api/v1/posts/-/feed",
            params={"mode": "following", "page_size": 100},
        )
        assert following.status_code == 200, following.text
        following_items = following.json()
        assert followed_id in {item["id"] for item in following_items}
        assert other_id not in {item["id"] for item in following_items}
        assert all(
            item["author_id"] == author_user["id"] for item in following_items
        )

        recommended = follower.get(
            f"{BASE}/api/v1/posts/-/feed",
            params={"mode": "recommended", "page_size": 100},
        )
        assert recommended.status_code == 200, recommended.text
        recommended_item = next(
            item for item in recommended.json() if item["id"] == followed_id
        )
        assert recommended_item["ranking_reason"] == "followed_author"

        latest = follower.get(
            f"{BASE}/api/v1/posts/-/feed",
            params={"mode": "latest", "page_size": 100},
        )
        latest_ids = [item["id"] for item in latest.json()]
        assert latest_ids.index(other_id) < latest_ids.index(followed_id)
    finally:
        follower.close()
        author.close()
        other.close()


def test_following_feed_requires_login():
    with httpx.Client() as client:
        response = client.get(
            f"{BASE}/api/v1/posts/-/feed",
            params={"mode": "following"},
        )
        assert response.status_code == 401
