"""Integration tests for the patches voting API.

Requires the backend server at localhost:8000.
Start: cd backend && uvicorn app.main:app --reload --port 8000
"""

import asyncio
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
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


def _expire_patch(patch_id: str) -> None:
    """Move a voting deadline into the past without changing its state."""
    database_url = os.environ["DATABASE_URL"].replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )

    async def expire() -> None:
        connection = await asyncpg.connect(database_url)
        try:
            await connection.execute(
                """
                UPDATE patch
                SET voting_ends_at = NOW() - INTERVAL '1 minute'
                WHERE id = $1
                """,
                UUID(patch_id),
            )
        finally:
            await connection.close()

    asyncio.run(expire())


def _patch_status(patch_id: str) -> str | None:
    database_url = os.environ["DATABASE_URL"].replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )

    async def read_status() -> str | None:
        connection = await asyncpg.connect(database_url)
        try:
            return await connection.fetchval(
                "SELECT status FROM patch WHERE id = $1",
                UUID(patch_id),
            )
        finally:
            await connection.close()

    return asyncio.run(read_status())


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

    def test_concurrent_active_pr_creation_is_serialized(self):
        first_client = httpx.Client()
        second_client = httpx.Client()
        try:
            first = _register(first_client, "pr-racer-a")
            second = _register(second_client, "pr-racer-b")
            first_headers = _login(first_client, first)
            second_headers = _login(second_client, second)
            payload = {
                "title": "Concurrent proposal",
                "content": "Only one should remain active.",
                "pr_number": _pr_number(),
            }

            def create(args: tuple[httpx.Client, dict[str, str]]) -> httpx.Response:
                client, headers = args
                return client.post(
                    f"{BASE}/api/v1/patches",
                    json=payload,
                    headers=headers,
                )

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(
                    pool.map(create, ((first_client, first_headers), (second_client, second_headers)))
                )

            assert sorted(result.status_code for result in results) == [201, 409]
            conflict = next(result for result in results if result.status_code == 409)
            assert conflict.json()["detail"] == "PATCH_PR_ALREADY_ACTIVE"
        finally:
            first_client.close()
            second_client.close()

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
        r = self.client.get(f"{BASE}/api/v1/patches/{pid}", headers=headers)
        assert r.status_code == 200
        assert r.json()["id"] == pid
        assert r.json()["status"] == "draft"

    def test_drafts_are_visible_only_to_their_author(self):
        author = _register(self.client, "draft-author")
        author_headers = _login(self.client, author)
        create = self.client.post(
            f"{BASE}/api/v1/patches",
            json={
                "title": "Private draft",
                "content": "Not ready for public review",
                "pr_number": _pr_number(),
            },
            headers=author_headers,
        )
        assert create.status_code == 201
        patch_id = create.json()["id"]

        draft_comment = self.client.post(
            f"{BASE}/api/v1/patches/{patch_id}/comments",
            headers=author_headers,
            json={"content": "Private draft discussion"},
        )
        assert draft_comment.status_code == 201
        comment_id = draft_comment.json()["id"]

        with httpx.Client() as anonymous:
            listing = anonymous.get(f"{BASE}/api/v1/patches")
            detail = anonymous.get(f"{BASE}/api/v1/patches/{patch_id}")
            feed = anonymous.get(f"{BASE}/api/v1/posts/-/feed")
            profile = anonymous.get(
                f"{BASE}/api/v1/users/{author['id']}/content"
            )
            comments = anonymous.get(
                f"{BASE}/api/v1/patches/{patch_id}/comments"
            )
            votes = anonymous.get(f"{BASE}/api/v1/patches/{patch_id}/votes")
        assert patch_id not in {item["id"] for item in listing.json()}
        assert detail.status_code == 404
        assert patch_id not in {item["id"] for item in feed.json()}
        assert patch_id not in {item["id"] for item in profile.json()}
        assert comments.status_code == 404
        assert votes.status_code == 404

        with httpx.Client() as other_client:
            other = _register(other_client, "draft-reader")
            other_headers = _login(other_client, other)
            other_listing = other_client.get(
                f"{BASE}/api/v1/patches",
                headers=other_headers,
            )
            other_detail = other_client.get(
                f"{BASE}/api/v1/patches/{patch_id}",
                headers=other_headers,
            )
            other_comment = other_client.post(
                f"{BASE}/api/v1/patches/{patch_id}/comments",
                headers=other_headers,
                json={"content": "Must stay private"},
            )
            other_vote = other_client.post(
                f"{BASE}/api/v1/patches/{patch_id}/vote",
                headers=other_headers,
                json={"choice": "for"},
            )
            other_like = other_client.put(
                f"{BASE}/api/v1/posts/{comment_id}/like",
                headers=other_headers,
            )
            other_unlike = other_client.delete(
                f"{BASE}/api/v1/posts/{comment_id}/like",
                headers=other_headers,
            )
            other_patch_report = other_client.post(
                f"{BASE}/api/v1/admin/reports",
                headers=other_headers,
                json={"patch_id": patch_id, "reason": "Private target"},
            )
            other_comment_report = other_client.post(
                f"{BASE}/api/v1/admin/reports",
                headers=other_headers,
                json={"content_id": comment_id, "reason": "Private target"},
            )
        assert patch_id not in {item["id"] for item in other_listing.json()}
        assert other_detail.status_code == 404
        assert other_comment.status_code == 404
        assert other_vote.status_code == 404
        assert other_like.status_code == 404
        assert other_unlike.status_code == 404
        assert other_patch_report.status_code == 404
        assert other_comment_report.status_code == 404

        author_detail = self.client.get(
            f"{BASE}/api/v1/patches/{patch_id}",
            headers=author_headers,
        )
        assert author_detail.status_code == 200

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

    def test_concurrent_submit_transitions_a_draft_once(self):
        user = _register(self.client, "submit-racer")
        headers = _login(self.client, user)
        create = self.client.post(
            f"{BASE}/api/v1/patches",
            json={
                "title": "One transition",
                "content": "Only one submit may win.",
                "pr_number": _pr_number(),
            },
            headers=headers,
        )
        assert create.status_code == 201
        patch_id = create.json()["id"]

        def submit_once(_: int) -> httpx.Response:
            with httpx.Client(timeout=10) as concurrent_client:
                return concurrent_client.post(
                    f"{BASE}/api/v1/patches/{patch_id}/submit",
                    headers=headers,
                )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit_once, range(2)))

        assert sorted(result.status_code for result in results) == [200, 422]
        assert _patch_status(patch_id) == "voting"

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

    def test_expired_patch_detail_tallies_without_losing_author(self):
        user = _register(self.client)
        headers = _login(self.client, user)
        create = self.client.post(
            f"{BASE}/api/v1/patches",
            json={
                "title": "Expired detail",
                "content": "Content",
                "pr_number": _pr_number(),
            },
            headers=headers,
        )
        pid = create.json()["id"]
        submit = self.client.post(
            f"{BASE}/api/v1/patches/{pid}/submit",
            headers=headers,
        )
        assert submit.status_code == 200
        _expire_patch(pid)

        def load_detail(_: int) -> httpx.Response:
            with httpx.Client(timeout=10) as concurrent_client:
                return concurrent_client.get(f"{BASE}/api/v1/patches/{pid}")

        with ThreadPoolExecutor(max_workers=2) as pool:
            details = list(pool.map(load_detail, range(2)))

        assert all(detail.status_code == 200 for detail in details)
        assert {detail.json()["status"] for detail in details} == {"rejected"}
        assert {
            detail.json()["author_username"] for detail in details
        } == {user["username"]}

    def test_expired_patch_is_tallied_without_page_traffic(self):
        user = _register(self.client)
        headers = _login(self.client, user)
        create = self.client.post(
            f"{BASE}/api/v1/patches",
            json={
                "title": "Scheduled tally",
                "content": "No page request should be required.",
                "pr_number": _pr_number(),
            },
            headers=headers,
        )
        patch_id = create.json()["id"]
        submit = self.client.post(
            f"{BASE}/api/v1/patches/{patch_id}/submit",
            headers=headers,
        )
        assert submit.status_code == 200
        _expire_patch(patch_id)

        deadline = time.monotonic() + 6
        status = _patch_status(patch_id)
        while status == "voting" and time.monotonic() < deadline:
            time.sleep(0.25)
            status = _patch_status(patch_id)

        assert status == "rejected"

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
