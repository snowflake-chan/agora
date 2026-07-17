"""Integration tests for the patches voting API.

Requires the backend server to be running at localhost:8000.
Start with:  cd backend && uvicorn app.main:app --reload --port 8000
"""

import sys
from uuid import uuid4

import httpx

BASE = "http://localhost:8000"


def _unique(prefix: str) -> dict:
    uid = uuid4().hex[:8]
    return {
        "email": f"{prefix}-{uid}@test.dev",
        "username": f"{prefix}-{uid}",
        "password": "testpass123",
    }


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
        r = self.client.post(
            f"{BASE}/api/v1/patches",
            json={"title": "My patch", "content": "Content", "pr_number": 1},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["title"] == "My patch"
        assert data["status"] == "draft"
        assert data["pr_number"] == 1

    def test_create_patch_requires_auth(self):
        r = self.client.post(
            f"{BASE}/api/v1/patches",
            json={"title": "Test", "content": "Test", "pr_number": 1},
        )
        assert r.status_code == 401

    def test_list_patches(self):
        user = _register(self.client)
        headers = _login(self.client, user)
        self.client.post(
            f"{BASE}/api/v1/patches",
            json={"title": "List me", "content": "Content", "pr_number": 2},
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
            json={"title": "Get me", "content": "Content", "pr_number": 3},
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
            json={"title": "Delete me", "content": "Bye", "pr_number": 4},
            headers=headers,
        )
        pid = create.json()["id"]
        r = self.client.delete(f"{BASE}/api/v1/patches/{pid}", headers=headers)
        assert r.status_code == 204
        r = self.client.get(f"{BASE}/api/v1/patches/{pid}")
        assert r.status_code == 404

    def test_non_author_cannot_delete(self):
        user_a = _register(self.client)
        user_b = _register(self.client)
        ha = _login(self.client, user_a)
        hb = _login(self.client, user_b)
        create = self.client.post(
            f"{BASE}/api/v1/patches",
            json={"title": "Mine", "content": "Hands off", "pr_number": 5},
            headers=ha,
        )
        pid = create.json()["id"]
        r = self.client.delete(f"{BASE}/api/v1/patches/{pid}", headers=hb)
        assert r.status_code == 403

    # ── Voting flow ──

    def test_submit_for_voting(self):
        user = _register(self.client)
        headers = _login(self.client, user)
        create = self.client.post(
            f"{BASE}/api/v1/patches",
            json={"title": "Submit me", "content": "Content", "pr_number": 6},
            headers=headers,
        )
        pid = create.json()["id"]
        r = self.client.post(f"{BASE}/api/v1/patches/{pid}/submit", headers=headers)
        assert r.status_code == 200
        assert r.json()["status"] == "voting"

    def test_cast_and_change_vote(self):
        user = _register(self.client)
        headers = _login(self.client, user)
        create = self.client.post(
            f"{BASE}/api/v1/patches",
            json={"title": "Vote", "content": "Content", "pr_number": 7},
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
            json={"title": "Count", "content": "Content", "pr_number": 8},
            headers=h1,
        )
        pid = create.json()["id"]
        self.client.post(f"{BASE}/api/v1/patches/{pid}/submit", headers=h1)
        self.client.post(f"{BASE}/api/v1/patches/{pid}/vote", json={"choice": "for"}, headers=h1)
        self.client.post(
            f"{BASE}/api/v1/patches/{pid}/vote", json={"choice": "abstain"}, headers=h2,
        )

        # Check counts
        r = self.client.get(f"{BASE}/api/v1/patches/{pid}")
        assert r.json()["for_count"] == 1
        assert r.json()["against_count"] == 0
        assert r.json()["abstain_count"] == 1

        # Check vote list
        r = self.client.get(f"{BASE}/api/v1/patches/{pid}/votes")
        assert len(r.json()) == 2

    def test_close_rejected(self):
        """Tied vote → rejected."""
        u1 = _register(self.client)
        u2 = _register(self.client)
        h1 = _login(self.client, u1)
        h2 = _login(self.client, u2)

        create = self.client.post(
            f"{BASE}/api/v1/patches",
            json={"title": "Reject", "content": "Content", "pr_number": 9},
            headers=h1,
        )
        pid = create.json()["id"]
        self.client.post(f"{BASE}/api/v1/patches/{pid}/submit", headers=h1)
        self.client.post(f"{BASE}/api/v1/patches/{pid}/vote", json={"choice": "for"}, headers=h1)
        self.client.post(
            f"{BASE}/api/v1/patches/{pid}/vote", json={"choice": "against"}, headers=h2,
        )

        r = self.client.post(f"{BASE}/api/v1/patches/{pid}/close", headers=h1)
        assert r.status_code == 200
        assert r.json()["status"] == "rejected"

    def test_close_approve(self):
        """2 for, 1 abstain → for(2) > total/2(1.5) → merge attempted."""
        u1 = _register(self.client)
        u2 = _register(self.client)
        u3 = _register(self.client)
        h1 = _login(self.client, u1)
        h2 = _login(self.client, u2)
        h3 = _login(self.client, u3)

        create = self.client.post(
            f"{BASE}/api/v1/patches",
            json={"title": "Approve", "content": "Content", "pr_number": 10},
            headers=h1,
        )
        pid = create.json()["id"]
        self.client.post(f"{BASE}/api/v1/patches/{pid}/submit", headers=h1)
        self.client.post(f"{BASE}/api/v1/patches/{pid}/vote", json={"choice": "for"}, headers=h1)
        self.client.post(f"{BASE}/api/v1/patches/{pid}/vote", json={"choice": "for"}, headers=h2)
        self.client.post(
            f"{BASE}/api/v1/patches/{pid}/vote", json={"choice": "abstain"}, headers=h3,
        )

        r = self.client.post(f"{BASE}/api/v1/patches/{pid}/close", headers=h1)
        assert r.status_code == 200
        status = r.json()["status"]
        # Status depends on GitHub token & PR existence
        assert status in ("merged", "failed"), f"Unexpected status: {status}"

    # ── Error cases ──

    def test_error_cases(self):
        user = _register(self.client)
        headers = _login(self.client, user)

        create = self.client.post(
            f"{BASE}/api/v1/patches",
            json={"title": "Errors", "content": "Content", "pr_number": 11},
            headers=headers,
        )
        pid = create.json()["id"]

        # Vote on draft
        r = self.client.post(
            f"{BASE}/api/v1/patches/{pid}/vote", json={"choice": "for"}, headers=headers,
        )
        assert r.status_code == 422

        self.client.post(f"{BASE}/api/v1/patches/{pid}/submit", headers=headers)

        # Invalid vote choice
        r = self.client.post(
            f"{BASE}/api/v1/patches/{pid}/vote", json={"choice": "invalid"}, headers=headers,
        )
        assert r.status_code == 422

        # Non-author close
        other = _register(self.client)
        ho = _login(self.client, other)
        r = self.client.post(f"{BASE}/api/v1/patches/{pid}/close", headers=ho)
        assert r.status_code == 403

        # Delete during voting
        r = self.client.delete(f"{BASE}/api/v1/patches/{pid}", headers=headers)
        assert r.status_code == 422


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
