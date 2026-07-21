"""Integration coverage for immutable content and proposal edit history."""

import asyncio
import os
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest


pytestmark = pytest.mark.usefixtures("server")
BASE = "http://localhost:8000/api/v1"


def _account(prefix: str) -> tuple[httpx.Client, dict]:
    client = httpx.Client()
    suffix = uuid4().hex[:10]
    password = "testpass123"
    registered = client.post(
        f"{BASE}/auth/register",
        json={
            "email": f"{prefix}-{suffix}@test.dev",
            "username": f"{prefix}-{suffix}",
            "password": password,
        },
    )
    assert registered.status_code == 200, registered.text
    logged_in = client.post(
        f"{BASE}/auth/login",
        json={"email": registered.json()["email"], "password": password},
    )
    assert logged_in.status_code == 200, logged_in.text
    token = logged_in.cookies.get("Authorization")
    assert token
    client.headers["Cookie"] = f"Authorization={token}"
    return client, registered.json()


def _pr_number() -> int:
    return int(uuid4().hex[:7], 16) + 1


def _set_patch_status(patch_id: str, status: str) -> None:
    database_url = os.environ["DATABASE_URL"].replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )

    async def update() -> None:
        connection = await asyncpg.connect(database_url)
        try:
            await connection.execute(
                "UPDATE patch SET status = $1 WHERE id = $2",
                status,
                UUID(patch_id),
            )
        finally:
            await connection.close()

    asyncio.run(update())


def test_post_edits_archive_public_snapshots_and_lock_poll_context():
    author, author_data = _account("revision-post-author")
    viewer, _ = _account("revision-post-viewer")
    try:
        created = author.post(
            f"{BASE}/posts",
            json={
                "title": "Original title",
                "content": "Original body remains inspectable.",
                "tags": ["first", "history"],
            },
        )
        assert created.status_code == 201, created.text
        post_id = created.json()["id"]
        assert created.json()["revision_number"] == 1

        edited = author.patch(
            f"{BASE}/posts/{post_id}",
            json={
                "title": "Revised title",
                "content": "Revised body is the current version.",
                "tags": ["second"],
                "revision_number": 1,
            },
        )
        assert edited.status_code == 200, edited.text
        assert edited.json()["revision_number"] == 2
        assert edited.json()["moderation_status"] == "published"

        history = viewer.get(f"{BASE}/posts/{post_id}/history")
        assert history.status_code == 200, history.text
        assert len(history.json()) == 1
        first = history.json()[0]
        assert first["version"] == 1
        assert first["title"] == "Original title"
        assert first["content"] == "Original body remains inspectable."
        assert first["tags"] == ["first", "history"]
        assert first["editor_id"] == author_data["id"]

        second_edit = author.patch(
            f"{BASE}/posts/{post_id}",
            json={"content": "A third public version.", "revision_number": 2},
        )
        assert second_edit.status_code == 200, second_edit.text
        assert second_edit.json()["revision_number"] == 3
        versions = viewer.get(f"{BASE}/posts/{post_id}/history").json()
        assert [item["version"] for item in versions] == [2, 1]
        assert versions[0]["title"] == "Revised title"
        assert versions[0]["content"] == "Revised body is the current version."

        stale = author.patch(
            f"{BASE}/posts/{post_id}",
            json={"content": "A stale editor must not overwrite.", "revision_number": 2},
        )
        assert stale.status_code == 409
        assert stale.json()["detail"] == "CONTENT_EDIT_CONFLICT"

        forbidden = viewer.patch(
            f"{BASE}/posts/{post_id}",
            json={"content": "Another user cannot edit this.", "revision_number": 3},
        )
        assert forbidden.status_code == 403
        assert forbidden.json()["detail"] == "FORBIDDEN"

        audited_delete = author.delete(f"{BASE}/posts/{post_id}")
        assert audited_delete.status_code == 409
        assert audited_delete.json()["detail"] == "AUDITED_CONTENT_DELETE_LOCKED"

        poll = author.post(
            f"{BASE}/posts",
            json={
                "title": "Locked poll context",
                "content": "The surrounding statement cannot move after votes.",
                "poll": {
                    "question": "Which stable option is preferred?",
                    "options": ["Option one", "Option two"],
                    "duration_hours": 24,
                },
            },
        )
        assert poll.status_code == 201, poll.text
        locked = author.patch(
            f"{BASE}/posts/{poll.json()['id']}",
            json={"content": "A bait-and-switch attempt.", "revision_number": 1},
        )
        assert locked.status_code == 409
        assert locked.json()["detail"] == "POLL_CONTENT_EDIT_LOCKED"
        poll_delete = author.delete(f"{BASE}/posts/{poll.json()['id']}")
        assert poll_delete.status_code == 409
        assert poll_delete.json()["detail"] == "POLL_CONTENT_DELETE_LOCKED"
        assert author.get(
            f"{BASE}/posts/{poll.json()['id']}/history"
        ).json() == []
    finally:
        author.close()
        viewer.close()


def test_private_revisions_never_leak_through_public_history():
    author, _ = _account("revision-private-author")
    try:
        created = author.post(
            f"{BASE}/posts",
            json={
                "title": "A normal public note",
                "content": "This version is initially public.",
            },
        )
        assert created.status_code == 201, created.text
        post_id = created.json()["id"]

        held = author.patch(
            f"{BASE}/posts/{post_id}",
            json={
                "content": "Government election policy details require review.",
                "revision_number": 1,
            },
        )
        assert held.status_code == 200, held.text
        assert held.json()["moderation_status"] == "pending_review"

        with httpx.Client() as anonymous:
            assert anonymous.get(f"{BASE}/posts/{post_id}").status_code == 404
            assert anonymous.get(f"{BASE}/posts/{post_id}/history").status_code == 404

        owner_history = author.get(f"{BASE}/posts/{post_id}/history")
        assert owner_history.status_code == 200, owner_history.text
        assert len(owner_history.json()) == 1
        assert owner_history.json()[0]["content"] == "This version is initially public."
    finally:
        author.close()


def test_comment_and_guild_discussion_edits_use_the_same_history_boundary():
    author, _ = _account("revision-comment-author")
    member, _ = _account("revision-guild-member")
    outsider, _ = _account("revision-outsider")
    try:
        post = author.post(
            f"{BASE}/posts",
            json={"title": "Comment root", "content": "A public root post."},
        )
        assert post.status_code == 201, post.text
        comment = author.post(
            f"{BASE}/posts/{post.json()['id']}/comments",
            json={"content": "First public comment."},
        )
        assert comment.status_code == 201, comment.text
        comment_id = comment.json()["id"]
        changed_comment = author.patch(
            f"{BASE}/posts/{comment_id}",
            json={"content": "Corrected public comment.", "revision_number": 1},
        )
        assert changed_comment.status_code == 200, changed_comment.text
        assert changed_comment.json()["revision_number"] == 2
        public_comment_history = outsider.get(
            f"{BASE}/posts/{comment_id}/history"
        )
        assert public_comment_history.status_code == 200, public_comment_history.text
        assert public_comment_history.json()[0]["content"] == "First public comment."

        guild = author.post(
            f"{BASE}/guilds",
            json={"name": f"Revision Guild {uuid4().hex[:8]}"},
        )
        assert guild.status_code == 200, guild.text
        guild_id = guild.json()["id"]
        discussion = author.post(
            f"{BASE}/guilds/{guild_id}/discussions",
            json={"title": "First topic", "content": "Original guild discussion."},
        )
        assert discussion.status_code == 200, discussion.text
        discussion_id = discussion.json()["id"]
        edited = author.patch(
            f"{BASE}/posts/{discussion_id}",
            json={
                "title": "Corrected topic",
                "content": "Corrected guild discussion.",
                "revision_number": 1,
            },
        )
        assert edited.status_code == 200, edited.text
        assert edited.json()["revision_number"] == 2
        assert outsider.get(f"{BASE}/posts/{discussion_id}/history").status_code == 404

        joined = member.post(f"{BASE}/guilds/{guild_id}/join")
        assert joined.status_code == 200, joined.text
        requests = author.get(f"{BASE}/guilds/{guild_id}/requests")
        request_id = requests.json()[0]["id"]
        approved = author.post(
            f"{BASE}/guilds/{guild_id}/requests/{request_id}/approve"
        )
        assert approved.status_code == 200, approved.text
        member_history = member.get(f"{BASE}/posts/{discussion_id}/history")
        assert member_history.status_code == 200, member_history.text
        assert member_history.json()[0]["title"] == "First topic"
        assert member_history.json()[0]["content"] == "Original guild discussion."
    finally:
        author.close()
        member.close()
        outsider.close()


def test_patch_history_is_public_after_submission_and_edits_lock_after_draft():
    author, _ = _account("revision-patch-author")
    viewer, _ = _account("revision-patch-viewer")
    try:
        created = author.post(
            f"{BASE}/patches",
            json={
                "title": "Original proposal",
                "content": "Original proposal rationale.",
                "pr_number": _pr_number(),
            },
        )
        assert created.status_code == 201, created.text
        patch_id = created.json()["id"]
        assert created.json()["revision_number"] == 1

        edited = author.patch(
            f"{BASE}/patches/{patch_id}",
            json={
                "title": "Revised proposal",
                "content": "Revised proposal rationale.",
                "revision_number": 1,
            },
        )
        assert edited.status_code == 200, edited.text
        assert edited.json()["revision_number"] == 2
        own_history = author.get(f"{BASE}/patches/{patch_id}/history")
        assert own_history.status_code == 200, own_history.text
        assert own_history.json()[0]["version"] == 1
        assert own_history.json()[0]["title"] == "Original proposal"
        assert viewer.get(f"{BASE}/patches/{patch_id}/history").status_code == 404

        # The governance status is the serialization boundary with submit/vote.
        # A non-draft proposal cannot be edited by any request racing this state.
        _set_patch_status(patch_id, "merged")
        locked = author.patch(
            f"{BASE}/patches/{patch_id}",
            json={"content": "A last-second decision change.", "revision_number": 2},
        )
        assert locked.status_code == 409
        assert locked.json()["detail"] == "PATCH_EDIT_LOCKED"

        public_history = viewer.get(f"{BASE}/patches/{patch_id}/history")
        assert public_history.status_code == 200, public_history.text
        assert public_history.json()[0]["content"] == "Original proposal rationale."
    finally:
        author.close()
        viewer.close()
