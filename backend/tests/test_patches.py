"""Integration tests for the patches voting API.

Requires the backend server at localhost:8000.
Start: cd backend && uvicorn app.main:app --reload --port 8000
"""

import asyncio
import os
import sys
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest

pytestmark = pytest.mark.usefixtures("server")

BASE = "http://localhost:8000"


def _unique(prefix: str) -> dict:
    uid = uuid4().hex[:8]
    return {
        "email": f"{prefix}-{uid}@test.dev",
        "username": f"{prefix}-{uid}",
        "password": "testpass123",
    }


def _pr_number() -> int:
    """Return a positive number unique enough for a persistent test database."""
    return int(uuid4().hex[:7], 16) + 1


def _set_patch_status(patch_id: str, status: str) -> None:
    """Set up a completed governance state directly in the integration database."""
    database_url = os.environ["DATABASE_URL"].replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )

    async def update_status() -> None:
        connection = await asyncpg.connect(database_url)
        try:
            await connection.execute(
                "UPDATE patch SET status = $1 WHERE id = $2",
                status,
                UUID(patch_id),
            )
        finally:
            await connection.close()

    asyncio.run(update_status())


def _register(client: httpx.Client, prefix: str = "u") -> dict:
    data = _unique(prefix)
    r = client.post(f"{BASE}/api/v1/auth/register", json=data)
    assert r.status_code == 200, f"Register failed: {r.text}"
    return {**(r.json()), "password": data["password"]}


def _login(client: httpx.Client, user: dict) -> dict:
    r = client.post(
        f"{BASE}/api/v1/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    assert r.status_code == 200
    cookie = r.cookies.get("Authorization")
    return {"Cookie": f"Authorization={cookie}"}


class TestPatches:
    """Integration tests for patches API."""

    def setup_method(self):
        self.client = httpx.Client()

    def teardown_method(self):
        self.client.close()

    # ── CRUD ──

    def test_create_patch(self):
        user = _register(self.client)
        headers = _login(self.client, user)
        pr_number = _pr_number()
        r = self.client.post(
            f"{BASE}/api/v1/patches",
            json={"title": "My patch", "content": "Content", "pr_number": pr_number},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["title"] == "My patch"
        assert data["status"] == "draft"
        assert data["pr_number"] == pr_number

    def test_create_patch_requires_auth(self):
        r = self.client.post(
            f"{BASE}/api/v1/patches",
            json={"title": "Test", "content": "Test", "pr_number": _pr_number()},
        )
        assert r.status_code == 401

    def test_cannot_create_two_active_patches_for_same_pr(self):
        user = _register(self.client)
        headers = _login(self.client, user)
        pr_number = _pr_number()
        payload = {"title": "First", "content": "Content", "pr_number": pr_number}

        first = self.client.post(
            f"{BASE}/api/v1/patches", json=payload, headers=headers
        )
        second = self.client.post(
            f"{BASE}/api/v1/patches",
            json={**payload, "title": "Duplicate"},
            headers=headers,
        )

        assert first.status_code == 201
        assert second.status_code == 409
        assert second.json()["detail"] == "PATCH_PR_ALREADY_ACTIVE"

    def test_rejected_pr_can_be_proposed_again(self):
        user = _register(self.client)
        headers = _login(self.client, user)
        pr_number = _pr_number()
        payload = {
            "title": "First attempt",
            "content": "Content",
            "pr_number": pr_number,
        }

        first = self.client.post(
            f"{BASE}/api/v1/patches", json=payload, headers=headers
        )
        assert first.status_code == 201
        _set_patch_status(first.json()["id"], "rejected")

        second = self.client.post(
            f"{BASE}/api/v1/patches",
            json={**payload, "title": "Revised proposal"},
            headers=headers,
        )

        assert second.status_code == 201
        assert second.json()["pr_number"] == pr_number

    def test_list_patches(self):
        user = _register(self.client)
        headers = _login(self.client, user)
        self.client.post(
            f"{BASE}/api/v1/patches",
            json={"title": "List me", "content": "Content", "pr_number": _pr_number()},
            headers=headers,
        )
        r = self.client.get(f"{BASE}/api/v1/patches")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        assert data[0]["for_count"] == 0

    def test_get_patch(self):
        user = _register(self.client)
        headers = _login(self.client, user)
        create = self.client.post(
            f"{BASE}/api/v1/patches",
            json={"title": "Get me", "content": "Content", "pr_number": _pr_number()},
            headers=headers,
        )
        pid = create.json()["id"]
        r = self.client.get(f"{BASE}/api/v1/patches/{pid}")
        assert r.status_code == 200
        assert r.json()["id"] == pid
        assert r.json()["status"] == "draft"

    def test_delete_draft(self):
        user = _register(self.client)
        headers = _login(self.client, user)
        create = self.client.post(
            f"{BASE}/api/v1/patches",
            json={"title": "Delete me", "content": "Bye", "pr_number": _pr_number()},
            headers=headers,
        )
        pid = create.json()["id"]
        r = self.client.delete(f"{BASE}/api/v1/patches/{pid}", headers=headers)
        assert r.status_code == 204
        r = self.client.get(f"{BASE}/api/v1/patches/{pid}")
        assert r.status_code == 404

    def test_non_author_cannot_delete(self):
        ua = _register(self.client)
        ub = _register(self.client)
        ha = _login(self.client, ua)
        hb = _login(self.client, ub)
        create = self.client.post(
            f"{BASE}/api/v1/patches",
            json={"title": "Mine", "content": "Hands off", "pr_number": _pr_number()},
            headers=ha,
        )
        pid = create.json()["id"]
        r = self.client.delete(f"{BASE}/api/v1/patches/{pid}", headers=hb)
        assert r.status_code == 403

    # ── Voting flow ──

    def test_submit_sets_voting_ends_at(self):
        """Submit sets voting_ends_at to ~3 days in the future."""
        user = _register(self.client)
        headers = _login(self.client, user)
        create = self.client.post(
            f"{BASE}/api/v1/patches",
            json={"title": "Deadline", "content": "Content", "pr_number": _pr_number()},
            headers=headers,
        )
        pid = create.json()["id"]
        r = self.client.post(f"{BASE}/api/v1/patches/{pid}/submit", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "voting"
        assert data["voting_ends_at"] is not None

    def test_cast_and_change_vote(self):
        user = _register(self.client)
        headers = _login(self.client, user)
        create = self.client.post(
            f"{BASE}/api/v1/patches",
            json={"title": "Vote", "content": "Content", "pr_number": _pr_number()},
            headers=headers,
        )
        pid = create.json()["id"]
        self.client.post(f"{BASE}/api/v1/patches/{pid}/submit", headers=headers)

        r = self.client.post(
            f"{BASE}/api/v1/patches/{pid}/vote", json={"choice": "for"}, headers=headers,
        )
        assert r.status_code == 201
        assert r.json()["choice"] == "for"

        # Change vote
        r = self.client.post(
            f"{BASE}/api/v1/patches/{pid}/vote", json={"choice": "against"}, headers=headers,
        )
        assert r.status_code == 201
        assert r.json()["choice"] == "against"

        r = self.client.get(f"{BASE}/api/v1/patches/{pid}")
        assert r.json()["for_count"] == 0
        assert r.json()["against_count"] == 1

    def test_vote_counts_and_list(self):
        u1 = _register(self.client)
        u2 = _register(self.client)
        h1 = _login(self.client, u1)
        h2 = _login(self.client, u2)

        create = self.client.post(
            f"{BASE}/api/v1/patches",
            json={"title": "Count", "content": "Content", "pr_number": _pr_number()},
            headers=h1,
        )
        pid = create.json()["id"]
        self.client.post(f"{BASE}/api/v1/patches/{pid}/submit", headers=h1)
        self.client.post(f"{BASE}/api/v1/patches/{pid}/vote", json={"choice": "for"}, headers=h1)
        self.client.post(
            f"{BASE}/api/v1/patches/{pid}/vote", json={"choice": "abstain"}, headers=h2,
        )

        r = self.client.get(f"{BASE}/api/v1/patches/{pid}")
        assert r.json()["for_count"] == 1
        assert r.json()["abstain_count"] == 1

        r = self.client.get(f"{BASE}/api/v1/patches/{pid}/votes")
        assert len(r.json()) == 2

    def test_cannot_vote_on_draft(self):
        user = _register(self.client)
        headers = _login(self.client, user)
        create = self.client.post(
            f"{BASE}/api/v1/patches",
            json={"title": "Draft vote", "content": "Content", "pr_number": _pr_number()},
            headers=headers,
        )
        pid = create.json()["id"]
        r = self.client.post(
            f"{BASE}/api/v1/patches/{pid}/vote", json={"choice": "for"}, headers=headers,
        )
        assert r.status_code == 422

    def test_invalid_vote_choice(self):
        user = _register(self.client)
        headers = _login(self.client, user)
        create = self.client.post(
            f"{BASE}/api/v1/patches",
            json={"title": "Bad vote", "content": "Content", "pr_number": _pr_number()},
            headers=headers,
        )
        pid = create.json()["id"]
        self.client.post(f"{BASE}/api/v1/patches/{pid}/submit", headers=headers)
        r = self.client.post(
            f"{BASE}/api/v1/patches/{pid}/vote", json={"choice": "invalid"}, headers=headers,
        )
        assert r.status_code == 422

    def test_cannot_delete_after_submit(self):
        user = _register(self.client)
        headers = _login(self.client, user)
        create = self.client.post(
            f"{BASE}/api/v1/patches",
            json={"title": "No delete", "content": "Content", "pr_number": _pr_number()},
            headers=headers,
        )
        pid = create.json()["id"]
        self.client.post(f"{BASE}/api/v1/patches/{pid}/submit", headers=headers)
        r = self.client.delete(f"{BASE}/api/v1/patches/{pid}", headers=headers)
        assert r.status_code == 422

    def test_close_endpoint_removed(self):
        """The /close endpoint should return 404."""
        user = _register(self.client)
        headers = _login(self.client, user)
        create = self.client.post(
            f"{BASE}/api/v1/patches",
            json={"title": "No close", "content": "Content", "pr_number": _pr_number()},
            headers=headers,
        )
        pid = create.json()["id"]
        self.client.post(f"{BASE}/api/v1/patches/{pid}/submit", headers=headers)
        r = self.client.post(f"{BASE}/api/v1/patches/{pid}/close", headers=headers)
        assert r.status_code == 404


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
