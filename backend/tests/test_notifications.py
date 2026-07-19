"""Integration tests for notification unread-count consistency."""

from uuid import uuid4

import httpx

BASE = "http://localhost:8000"


def _register(client: httpx.Client, prefix: str) -> dict:
    uid = uuid4().hex[:8]
    data = {
        "email": f"{prefix}-{uid}@test.dev",
        "username": f"{prefix}-{uid}",
        "password": "testpass123",
    }
    response = client.post(f"{BASE}/api/v1/auth/register", json=data)
    assert response.status_code == 200, response.text
    return {**response.json(), "password": data["password"]}


def _login(client: httpx.Client, user: dict) -> dict:
    response = client.post(
        f"{BASE}/api/v1/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    assert response.status_code == 200, response.text
    return {"Cookie": f"Authorization={response.cookies['Authorization']}"}


def test_mark_one_read_is_idempotent():
    with httpx.Client() as client:
        author = _register(client, "notif-author")
        voter = _register(client, "notif-voter")
        author_headers = _login(client, author)
        voter_headers = _login(client, voter)

        created = client.post(
            f"{BASE}/api/v1/patches",
            json={"title": "Notify me", "content": "Content", "pr_number": 9001},
            headers=author_headers,
        )
        assert created.status_code == 201, created.text
        patch_id = created.json()["id"]
        submitted = client.post(
            f"{BASE}/api/v1/patches/{patch_id}/submit",
            headers=author_headers,
        )
        assert submitted.status_code == 200, submitted.text
        voted = client.post(
            f"{BASE}/api/v1/patches/{patch_id}/vote",
            json={"choice": "for"},
            headers=voter_headers,
        )
        assert voted.status_code == 201, voted.text

        notifications = client.get(
            f"{BASE}/api/v1/notifications",
            headers=author_headers,
        )
        assert notifications.status_code == 200, notifications.text
        payload = notifications.json()
        assert payload["unread_count"] == 1
        notification_id = payload["items"][0]["id"]

        first = client.patch(
            f"{BASE}/api/v1/notifications/{notification_id}/read",
            headers=author_headers,
        )
        second = client.patch(
            f"{BASE}/api/v1/notifications/{notification_id}/read",
            headers=author_headers,
        )
        assert first.status_code == 204
        assert second.status_code == 204

        unread = client.get(
            f"{BASE}/api/v1/notifications/unread-count",
            headers=author_headers,
        )
        assert unread.status_code == 200
        assert unread.json()["count"] == 0
