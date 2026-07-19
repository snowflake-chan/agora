"""Integration tests for traceable patch discussions."""

from uuid import uuid4

import httpx


BASE = "http://localhost:8000"


def _authenticated_client() -> httpx.Client:
    client = httpx.Client()
    uid = uuid4().hex[:8]
    email = f"discussion-{uid}@test.dev"
    password = "testpass123"
    registered = client.post(
        f"{BASE}/api/v1/auth/register",
        json={
            "email": email,
            "username": f"discussion-{uid}",
            "password": password,
        },
    )
    assert registered.status_code == 200, registered.text
    logged_in = client.post(
        f"{BASE}/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert logged_in.status_code == 200, logged_in.text
    return client


def test_patch_comments_are_traceable_and_reactable():
    with _authenticated_client() as client:
        patch = client.post(
            f"{BASE}/api/v1/patches",
            json={
                "title": "Discussion test",
                "content": "Review context",
                "pr_number": 999001,
            },
        )
        assert patch.status_code == 201, patch.text
        patch_id = patch.json()["id"]

        root = client.post(
            f"{BASE}/api/v1/patches/{patch_id}/comments",
            json={"content": "Original review point"},
        )
        assert root.status_code == 201, root.text
        root_id = root.json()["id"]

        reply = client.post(
            f"{BASE}/api/v1/patches/{patch_id}/comments",
            json={"content": "Follow-up", "replying_id": root_id},
        )
        assert reply.status_code == 201, reply.text

        liked = client.put(f"{BASE}/api/v1/posts/{root_id}/like")
        assert liked.json() == {"like_count": 1, "liked_by_me": True}

        comments = client.get(
            f"{BASE}/api/v1/patches/{patch_id}/comments"
        ).json()
        assert comments[0]["reply_count"] == 1
        assert comments[0]["like_count"] == 1
        assert comments[1]["replying_to_content"] == "Original review point"

        detail = client.get(f"{BASE}/api/v1/patches/{patch_id}").json()
        assert detail["comment_count"] == 2


def test_patch_comment_requires_auth():
    with httpx.Client() as client:
        missing = client.post(
            f"{BASE}/api/v1/patches/{uuid4()}/comments",
            json={"content": "No session"},
        )
        assert missing.status_code == 401
