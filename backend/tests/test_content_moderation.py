"""Integration coverage for automated moderation visibility and review."""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.content_moderation import hold_translation_source_for_review


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
    login = client.post(
        f"{BASE}/auth/login",
        json={"email": registered.json()["email"], "password": password},
    )
    assert login.status_code == 200, login.text
    token = login.cookies.get("Authorization")
    assert token
    client.headers["Cookie"] = f"Authorization={token}"
    return client, registered.json()


def _database_url() -> str:
    return os.environ["DATABASE_URL"].replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )


def _set_role(user_id: str, role: str) -> None:
    async def update_role() -> None:
        connection = await asyncpg.connect(_database_url())
        try:
            await connection.execute(
                'UPDATE "user" SET role = $1 WHERE id = $2',
                role,
                UUID(user_id),
            )
        finally:
            await connection.close()

    asyncio.run(update_role())


def _set_patch_status(patch_id: str, status: str) -> None:
    async def update_status() -> None:
        connection = await asyncpg.connect(_database_url())
        try:
            await connection.execute(
                "UPDATE patch SET status = $1 WHERE id = $2",
                status,
                UUID(patch_id),
            )
        finally:
            await connection.close()

    asyncio.run(update_status())


def _set_content_moderation_status(content_id: str, status: str) -> None:
    async def update_status() -> None:
        connection = await asyncpg.connect(_database_url())
        try:
            await connection.execute(
                "UPDATE content SET moderation_status = $1 WHERE id = $2",
                status,
                UUID(content_id),
            )
        finally:
            await connection.close()

    asyncio.run(update_status())


async def _hold_translation_source(**kwargs) -> bool:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            held = await hold_translation_source_for_review(session, **kwargs)
            return held is not None
    finally:
        await engine.dispose()


def test_translation_verdict_holds_only_the_current_canonical_source():
    author, author_user = _account("ai-source-author")
    viewer, viewer_user = _account("ai-source-viewer")
    created = author.post(
        f"{BASE}/posts",
        json={"title": "Release candidate", "content": "Fast window"},
    )
    assert created.status_code == 201, created.text
    post = created.json()
    content_id = UUID(post["id"])

    async def hold_once(
        *,
        revision: int,
        body: str,
        actor_id: UUID,
        provenance: str = "provider",
    ) -> bool:
        return await _hold_translation_source(
            content_id=content_id,
            revision_number=revision,
            context="post",
            fields=[("title", "Release candidate"), ("body", body)],
            reason="political_or_uncertain",
            verdict_provenance=provenance,
            actor_id=actor_id,
        )

    author_id = UUID(author_user["id"])
    viewer_id = UUID(viewer_user["id"])
    assert asyncio.run(
        hold_once(revision=2, body="Fast window", actor_id=author_id)
    ) is False
    assert asyncio.run(
        hold_once(revision=1, body="Mismatched text", actor_id=author_id)
    ) is False
    # No viewer-triggered translation may hide another author's content,
    # regardless of which semantic engine produced the verdict.
    assert asyncio.run(
        hold_once(revision=1, body="Fast window", actor_id=viewer_id)
    ) is False
    assert asyncio.run(
        hold_once(
            revision=1,
            body="Fast window",
            actor_id=viewer_id,
            provenance="trusted_classifier",
        )
    ) is False

    async def race_holds() -> list[bool]:
        return list(
            await asyncio.gather(
                hold_once(
                    revision=1,
                    body="Fast window",
                    actor_id=author_id,
                ),
                hold_once(
                    revision=1,
                    body="Fast window",
                    actor_id=author_id,
                ),
            )
        )

    assert asyncio.run(race_holds()).count(True) == 1
    own_detail = author.get(f"{BASE}/posts/{content_id}")
    assert own_detail.status_code == 200, own_detail.text
    assert own_detail.json()["moderation_status"] == "pending_review"
    assert own_detail.json()["moderation_reason"] == "political_or_uncertain"
    assert viewer.get(f"{BASE}/posts/{content_id}").status_code == 404


def test_translation_verdict_does_not_override_approved_revision():
    author, author_user = _account("ai-approved-author")
    created = author.post(
        f"{BASE}/posts",
        json={"title": "Approved release", "content": "Candidate build"},
    )
    assert created.status_code == 201, created.text
    content_id = created.json()["id"]
    _set_content_moderation_status(content_id, "approved")

    async def try_hold() -> bool:
        return await _hold_translation_source(
            content_id=UUID(content_id),
            revision_number=1,
            context="post",
            fields=[
                ("title", "Approved release"),
                ("body", "Candidate build"),
            ],
            reason="political_or_uncertain",
            verdict_provenance="provider",
            actor_id=UUID(author_user["id"]),
        )

    assert asyncio.run(try_hold()) is False
    detail = author.get(f"{BASE}/posts/{content_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["moderation_status"] == "approved"


def test_reapproval_does_not_reopen_a_previously_public_poll():
    author, author_user = _account("ai-existing-poll-author")
    admin, admin_user = _account("ai-existing-poll-admin")
    _set_role(admin_user["id"], "super_admin")

    created = author.post(
        f"{BASE}/posts",
        json={
            "title": "Existing release poll",
            "content": "Choose the candidate build.",
            "poll": {
                "question": "Which build should ship?",
                "options": ["Stable", "Candidate"],
                "duration_hours": 24,
            },
        },
    )
    assert created.status_code == 201, created.text
    post_id = created.json()["id"]

    held = asyncio.run(
        _hold_translation_source(
            content_id=UUID(post_id),
            revision_number=1,
            context="post",
            fields=[
                ("title", "Existing release poll"),
                ("body", "Choose the candidate build."),
            ],
            reason="political_or_uncertain",
            verdict_provenance="provider",
            actor_id=UUID(author_user["id"]),
        )
    )
    assert held is True
    old_dates = _expire_pending_poll_and_backdate_post(post_id)

    approved = admin.post(
        f"{BASE}/admin/moderation/{post_id}/review",
        json={
            "decision": "approve",
            "note": "The release terminology is non-political.",
            "revision_number": 1,
        },
    )
    assert approved.status_code == 200, approved.text

    detail = author.get(f"{BASE}/posts/{post_id}")
    assert detail.status_code == 200, detail.text
    poll = detail.json()["poll"]
    assert poll["is_closed"] is True
    assert datetime.fromisoformat(poll["closes_at"]) == old_dates["poll"]["closes_at"]


def test_pending_translation_delivery_is_recoverable_and_idempotent():
    author, author_user = _account("ai-pending-delivery-author")
    created = author.post(
        f"{BASE}/posts",
        json={
            "title": "Recoverable moderation delivery",
            "content": "A canonical source awaiting a durable signal.",
        },
    )
    assert created.status_code == 201, created.text
    post_id = created.json()["id"]

    held = asyncio.run(
        _hold_translation_source(
            content_id=UUID(post_id),
            revision_number=1,
            context="post",
            fields=[
                ("title", "Recoverable moderation delivery"),
                ("body", "A canonical source awaiting a durable signal."),
            ],
            reason="political_or_uncertain",
            verdict_provenance="provider",
            actor_id=UUID(author_user["id"]),
        )
    )
    assert held is True
    assert _content_delivery_state(post_id)["moderation_effects_completed_at"] is None

    _run_delivery_reconciliation_twice()

    pending_notifications = [
        item
        for item in author.get(f"{BASE}/notifications").json()["items"]
        if item["type"] == "moderation_pending"
        and item["link"] == f"/posts/{post_id}"
    ]
    assert len(pending_notifications) == 1
    assert (
        _content_delivery_state(post_id)["moderation_effects_completed_at"]
        is not None
    )


def _expire_pending_poll_and_backdate_post(post_id: str) -> dict:
    async def update_dates() -> dict:
        connection = await asyncpg.connect(_database_url())
        try:
            content = await connection.fetchrow(
                """
                UPDATE content
                SET created_at = clock_timestamp() - INTERVAL '30 days'
                WHERE id = $1
                RETURNING created_at
                """,
                UUID(post_id),
            )
            poll = await connection.fetchrow(
                """
                UPDATE post_poll
                SET created_at = clock_timestamp() - INTERVAL '48 hours',
                    closes_at = clock_timestamp() - INTERVAL '24 hours'
                WHERE post_id = $1
                RETURNING created_at, closes_at
                """,
                UUID(post_id),
            )
            return {"content": content, "poll": poll}
        finally:
            await connection.close()

    return asyncio.run(update_dates())


def _stage_approval_without_delivery(content_id: str, reviewer_id: str) -> None:
    async def update_status() -> None:
        connection = await asyncpg.connect(_database_url())
        try:
            await connection.execute(
                """
                UPDATE content
                SET moderation_status = 'approved',
                    moderation_review_note = 'Recovered after interruption.',
                    moderation_reviewed_by = $2,
                    moderation_reviewed_at = clock_timestamp(),
                    published_at = clock_timestamp(),
                    moderation_effects_completed_at = NULL
                WHERE id = $1
                """,
                UUID(content_id),
                UUID(reviewer_id),
            )
        finally:
            await connection.close()

    asyncio.run(update_status())


def _clear_delivery_marker(content_id: str) -> None:
    async def update_status() -> None:
        connection = await asyncpg.connect(_database_url())
        try:
            await connection.execute(
                """
                UPDATE content
                SET moderation_effects_completed_at = NULL
                WHERE id = $1
                """,
                UUID(content_id),
            )
        finally:
            await connection.close()

    asyncio.run(update_status())


def _content_delivery_state(content_id: str) -> dict:
    async def fetch_state() -> dict:
        connection = await asyncpg.connect(_database_url())
        try:
            row = await connection.fetchrow(
                """
                SELECT created_at, published_at, moderation_reviewed_at,
                       moderation_effects_completed_at
                FROM content
                WHERE id = $1
                """,
                UUID(content_id),
            )
            return dict(row)
        finally:
            await connection.close()

    return asyncio.run(fetch_state())


def _run_delivery_reconciliation_twice() -> None:
    async def reconcile() -> None:
        from app.db import async_session
        from app.moderation_delivery import reconcile_moderation_effects_once

        try:
            await reconcile_moderation_effects_once()
            await reconcile_moderation_effects_once()
        finally:
            maker = async_session._maker
            if maker is not None:
                await maker.kw["bind"].dispose()
                async_session._maker = None

    asyncio.run(reconcile())


def test_flagged_post_is_author_only_until_atomic_approval():
    author, author_user = _account("review-author")
    viewer, _ = _account("review-viewer")
    admin, admin_user = _account("review-admin")
    _set_role(admin_user["id"], "moderator")

    try:
        followed = viewer.put(f"{BASE}/users/{author_user['id']}/follow")
        assert followed.status_code == 200, followed.text

        created = author.post(
            f"{BASE}/posts",
            json={
                "title": "[test:political] Government election policy discussion",
                "content": "[test:political] A topic that requires a human review.",
                "tags": ["public policy"],
                "poll": {
                "question": "[test:political] Which policy should be reviewed?",
                    "options": ["First option", "Second option"],
                    "duration_hours": 24,
                },
            },
        )
        assert created.status_code == 201, created.text
        pending = created.json()
        post_id = pending["id"]
        assert pending["moderation_status"] == "pending_review"
        assert pending["moderation_reason"] == "political_or_uncertain"

        hidden_detail = viewer.get(f"{BASE}/posts/{post_id}")
        assert hidden_detail.status_code == 404
        hidden_delete = viewer.delete(f"{BASE}/posts/{post_id}")
        assert hidden_delete.status_code == 404
        with httpx.Client() as anonymous:
            assert anonymous.get(f"{BASE}/posts/{post_id}").status_code == 404
        assert post_id not in {
            item["id"] for item in viewer.get(f"{BASE}/posts").json()
        }
        assert post_id not in {
            item["id"] for item in viewer.get(f"{BASE}/posts/-/feed").json()
        }
        assert post_id not in {
            item["id"]
            for item in viewer.get(
                f"{BASE}/users/{author_user['id']}/posts"
            ).json()
        }

        author_detail = author.get(f"{BASE}/posts/{post_id}")
        assert author_detail.status_code == 200, author_detail.text
        assert author_detail.json()["moderation_status"] == "pending_review"
        staff_detail = admin.get(f"{BASE}/posts/{post_id}")
        assert staff_detail.status_code == 200, staff_detail.text
        assert staff_detail.json()["moderation_status"] == "pending_review"

        blocked_like = author.put(f"{BASE}/posts/{post_id}/like")
        assert blocked_like.status_code == 409
        assert blocked_like.json()["detail"] == "CONTENT_PENDING_REVIEW"
        blocked_reply = author.post(
            f"{BASE}/posts/{post_id}/comments",
            json={"content": "This must stay read-only while pending."},
        )
        assert blocked_reply.status_code == 409
        assert blocked_reply.json()["detail"] == "CONTENT_PENDING_REVIEW"
        blocked_vote = author.put(
            f"{BASE}/posts/{post_id}/poll/vote",
            json={"option_id": pending["poll"]["options"][0]["id"]},
        )
        assert blocked_vote.status_code == 409
        assert blocked_vote.json()["detail"] == "CONTENT_PENDING_REVIEW"
        hidden_report = viewer.post(
            f"{BASE}/admin/reports",
            json={"content_id": post_id, "reason": "Cannot report hidden content"},
        )
        assert hidden_report.status_code == 404

        follower_notifications = viewer.get(f"{BASE}/notifications").json()["items"]
        assert not any(
            item["type"] == "following_post"
            and item["link"] == f"/posts/{post_id}"
            for item in follower_notifications
        )

        queue = admin.get(f"{BASE}/admin/moderation").json()
        queued = next(item for item in queue if item["id"] == post_id)
        assert queued["content_type"] == "post"
        assert queued["moderation_reason"] == "political_or_uncertain"
        assert queued["poll_question"] == "[test:political] Which policy should be reviewed?"
        assert queued["poll_options"] == ["First option", "Second option"]
        pending_notification = next(
            item
            for item in author.get(f"{BASE}/notifications").json()["items"]
            if item["type"] == "moderation_pending"
            and item["link"] == f"/posts/{post_id}"
        )
        assert pending_notification["message"] == "political_or_uncertain"

        missing_note = admin.post(
            f"{BASE}/admin/moderation/{post_id}/review",
            json={"decision": "reject"},
        )
        assert missing_note.status_code == 422

        old_dates = _expire_pending_poll_and_backdate_post(post_id)
        assert old_dates["poll"]["closes_at"] < datetime.now().astimezone()
        control = author.post(
            f"{BASE}/posts",
            json={
                "title": "Publication-time ranking control",
                "content": "A normal post created after the held submission.",
            },
        )
        assert control.status_code == 201, control.text
        control_id = control.json()["id"]

        approved = admin.post(
            f"{BASE}/admin/moderation/{post_id}/review",
            json={"decision": "approve", "note": "Context is acceptable."},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["moderation_status"] == "approved"
        assert approved.json()["moderation_reviewed_by"] == admin_user["id"]
        assert approved.json()["moderation_reviewed_at"]

        approved_at = datetime.fromisoformat(
            approved.json()["moderation_reviewed_at"]
        )
        approved_detail = viewer.get(f"{BASE}/posts/{post_id}").json()
        assert approved_detail["poll"]["is_closed"] is False
        closes_at = datetime.fromisoformat(approved_detail["poll"]["closes_at"])
        assert 23.9 < (closes_at - approved_at).total_seconds() / 3600 < 24.1

        delivery_state = _content_delivery_state(post_id)
        assert delivery_state["created_at"] == old_dates["content"]["created_at"]
        assert delivery_state["published_at"] == delivery_state["moderation_reviewed_at"]
        assert delivery_state["moderation_effects_completed_at"] is not None

        latest_feed = viewer.get(
            f"{BASE}/posts/-/feed",
            params={"mode": "latest", "page_size": 100},
        ).json()
        feed_ids = [item["id"] for item in latest_feed]
        assert feed_ids.index(post_id) < feed_ids.index(control_id)
        approved_feed_item = next(
            item for item in latest_feed if item["id"] == post_id
        )
        feed_time = datetime.fromisoformat(approved_feed_item["created_at"])
        assert abs((feed_time - approved_at).total_seconds()) < 1

        repeated = admin.post(
            f"{BASE}/admin/moderation/{post_id}/review",
            json={"decision": "reject", "note": "Must not overwrite."},
        )
        assert repeated.status_code == 409
        assert repeated.json()["detail"] == "CONTENT_REVIEW_ALREADY_DECIDED"

        public_detail = viewer.get(f"{BASE}/posts/{post_id}")
        assert public_detail.status_code == 200, public_detail.text
        assert public_detail.json()["moderation_status"] == "published"
        assert public_detail.json()["moderation_reason"] is None
        assert public_detail.json()["moderation_review_note"] is None

        follower_notifications = viewer.get(f"{BASE}/notifications").json()["items"]
        assert any(
            item["type"] == "following_post"
            and item["link"] == f"/posts/{post_id}"
            for item in follower_notifications
        )
        author_notifications = author.get(f"{BASE}/notifications").json()["items"]
        assert {
            item["type"]
            for item in author_notifications
            if item["link"] == f"/posts/{post_id}"
        } >= {"moderation_pending", "moderation_approved"}
        approved_notification = next(
            item
            for item in author_notifications
            if item["type"] == "moderation_approved"
            and item["link"] == f"/posts/{post_id}"
        )
        assert approved_notification["message"] == "Context is acceptable."
    finally:
        author.close()
        viewer.close()
        admin.close()


def test_concurrent_review_preserves_the_first_decision_and_audit_fields():
    author, _ = _account("race-author")
    first_admin, first_user = _account("race-admin-a")
    second_admin, second_user = _account("race-admin-b")
    _set_role(first_user["id"], "moderator")
    _set_role(second_user["id"], "moderator")

    try:
        created = author.post(
            f"{BASE}/posts",
            json={
                "title": "[test:political] Government election review race",
                "content": "Only one moderator decision may win.",
            },
        )
        assert created.status_code == 201, created.text
        post_id = created.json()["id"]

        def approve() -> httpx.Response:
            return first_admin.post(
                f"{BASE}/admin/moderation/{post_id}/review",
                json={"decision": "approve", "note": "Approved by first reviewer."},
            )

        def reject() -> httpx.Response:
            return second_admin.post(
                f"{BASE}/admin/moderation/{post_id}/review",
                json={"decision": "reject", "note": "Rejected by second reviewer."},
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda operation: operation(), (approve, reject)))
        assert sorted(response.status_code for response in results) == [200, 409]

        winner = next(response.json() for response in results if response.status_code == 200)
        history = first_admin.get(
            f"{BASE}/admin/moderation",
            params={"status": winner["moderation_status"]},
        )
        assert history.status_code == 200, history.text
        stored = next(item for item in history.json() if item["id"] == post_id)
        assert stored["moderation_reviewed_by"] == winner["moderation_reviewed_by"]
        assert stored["moderation_review_note"] == winner["moderation_review_note"]
    finally:
        author.close()
        first_admin.close()
        second_admin.close()


def test_review_rejects_a_revision_changed_after_the_queue_was_opened():
    author, _ = _account("review-revision-author")
    admin, admin_user = _account("review-revision-admin")
    _set_role(admin_user["id"], "moderator")

    try:
        created = author.post(
            f"{BASE}/posts",
            json={
                "title": "[test:political] Government election review v1",
                "content": "[test:political] The first held version.",
            },
        )
        assert created.status_code == 201, created.text
        post_id = created.json()["id"]
        queue_item = next(
            item
            for item in admin.get(f"{BASE}/admin/moderation").json()
            if item["id"] == post_id
        )
        assert queue_item["revision_number"] == 1

        edited = author.patch(
            f"{BASE}/posts/{post_id}",
            json={
                "content": "[test:political] Government election review text changed after opening.",
                "revision_number": 1,
            },
        )
        assert edited.status_code == 200, edited.text
        assert edited.json()["revision_number"] == 2
        assert edited.json()["moderation_status"] == "pending_review"

        stale = admin.post(
            f"{BASE}/admin/moderation/{post_id}/review",
            json={"decision": "approve", "revision_number": 1},
        )
        assert stale.status_code == 409
        assert stale.json()["detail"] == "CONTENT_REVIEW_CONFLICT"

        fresh = admin.post(
            f"{BASE}/admin/moderation/{post_id}/review",
            json={"decision": "approve", "revision_number": 2},
        )
        assert fresh.status_code == 200, fresh.text
    finally:
        author.close()
        admin.close()


def test_corrected_public_content_keeps_its_original_feed_position():
    author, _ = _account("published-position-author")
    admin, admin_user = _account("published-position-admin")
    _set_role(admin_user["id"], "moderator")

    try:
        original = author.post(
            f"{BASE}/posts",
            json={"title": "Original position", "content": "Initially public."},
        )
        assert original.status_code == 201, original.text
        original_id = original.json()["id"]
        original_time = datetime.fromisoformat(original.json()["created_at"])
        if original_time.tzinfo is None:
            original_time = original_time.replace(tzinfo=timezone.utc)

        control = author.post(
            f"{BASE}/posts",
            json={"title": "Newer control", "content": "Published second."},
        )
        assert control.status_code == 201, control.text
        control_id = control.json()["id"]

        held = author.patch(
            f"{BASE}/posts/{original_id}",
            json={
                "content": "[test:political] Government election text requires review.",
                "revision_number": 1,
            },
        )
        assert held.status_code == 200, held.text
        assert held.json()["moderation_status"] == "pending_review"

        rejected = admin.post(
            f"{BASE}/admin/moderation/{original_id}/review",
            json={
                "decision": "reject",
                "note": "Remove the political passage.",
                "revision_number": 2,
            },
        )
        assert rejected.status_code == 200, rejected.text

        corrected = author.patch(
            f"{BASE}/posts/{original_id}",
            json={
                "content": "A corrected ordinary product note.",
                "revision_number": 2,
            },
        )
        assert corrected.status_code == 200, corrected.text
        assert corrected.json()["moderation_status"] == "published"

        latest = author.get(
            f"{BASE}/posts/-/feed",
            params={"mode": "latest", "page_size": 100},
        ).json()
        ids = [item["id"] for item in latest]
        assert ids.index(control_id) < ids.index(original_id)
        restored = next(item for item in latest if item["id"] == original_id)
        restored_time = datetime.fromisoformat(restored["created_at"])
        assert abs((restored_time - original_time).total_seconds()) < 1
    finally:
        author.close()
        admin.close()


def test_flagged_comment_has_no_public_count_trace_or_reply_notification():
    post_author, _ = _account("comment-root")
    commenter, _ = _account("comment-author")
    admin, admin_user = _account("comment-admin")
    _set_role(admin_user["id"], "moderator")

    try:
        post = post_author.post(
            f"{BASE}/posts",
            json={"title": "Ordinary topic", "content": "A normal public post."},
        )
        assert post.status_code == 201, post.text
        post_id = post.json()["id"]

        comment = commenter.post(
            f"{BASE}/posts/{post_id}/comments",
            json={"content": "[test:political] Government election politics need review."},
        )
        assert comment.status_code == 201, comment.text
        comment_id = comment.json()["id"]
        assert comment.json()["moderation_status"] == "pending_review"

        public_comments = post_author.get(f"{BASE}/posts/{post_id}/comments")
        assert public_comments.status_code == 200
        assert comment_id not in {item["id"] for item in public_comments.json()}
        assert post_author.get(f"{BASE}/posts/{post_id}").json()["reply_count"] == 0

        own_comments = commenter.get(f"{BASE}/posts/{post_id}/comments")
        own_pending = next(item for item in own_comments.json() if item["id"] == comment_id)
        assert own_pending["moderation_status"] == "pending_review"

        hidden_reply_target = post_author.post(
            f"{BASE}/posts/{post_id}/comments",
            json={"content": "Cannot reply to a hidden target.", "replying_id": comment_id},
        )
        assert hidden_reply_target.status_code == 404

        blocked_like = commenter.put(f"{BASE}/posts/{comment_id}/like")
        assert blocked_like.status_code == 409
        assert blocked_like.json()["detail"] == "CONTENT_PENDING_REVIEW"

        root_notifications = post_author.get(f"{BASE}/notifications").json()["items"]
        assert not any(item["link"].endswith(f"#{comment_id}") for item in root_notifications)

        rejected = admin.post(
            f"{BASE}/admin/moderation/{comment_id}/review",
            json={
                "decision": "reject",
                "note": "This discussion needs revision before publication.",
            },
        )
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["moderation_status"] == "rejected"

        still_hidden = post_author.get(f"{BASE}/posts/{post_id}/comments").json()
        assert comment_id not in {item["id"] for item in still_hidden}
        rejected_for_author = commenter.get(
            f"{BASE}/posts/{post_id}/comments"
        ).json()
        own_rejected = next(
            item for item in rejected_for_author if item["id"] == comment_id
        )
        assert own_rejected["moderation_status"] == "rejected"
        assert own_rejected["moderation_review_note"]
        rejected_notifications = commenter.get(
            f"{BASE}/notifications"
        ).json()["items"]
        rejected_notification = next(
            item
            for item in rejected_notifications
            if item["type"] == "moderation_rejected"
            and item["link"] == f"/posts/{post_id}#{comment_id}"
        )
        assert rejected_notification["message"] == (
            "This discussion needs revision before publication."
        )
    finally:
        post_author.close()
        commenter.close()
        admin.close()


def test_patch_comments_and_guild_discussions_share_the_review_gate():
    patch_author, patch_author_user = _account("surface-patch")
    commenter, _ = _account("surface-commenter")
    guild_member, guild_member_user = _account("surface-member")
    admin, admin_user = _account("surface-admin")
    _set_role(admin_user["id"], "moderator")

    try:
        patch = patch_author.post(
            f"{BASE}/patches",
            json={
                "title": "Review surface test",
                "content": "A draft used to test moderated discussion.",
                "pr_number": 10_000 + (int(uuid4().hex[:8], 16) % 1_000_000),
            },
        )
        assert patch.status_code == 201, patch.text
        patch_id = patch.json()["id"]

        draft_comment = patch_author.post(
            f"{BASE}/patches/{patch_id}/comments",
            json={"content": "[test:political] Government election draft review context."},
        )
        assert draft_comment.status_code == 201, draft_comment.text
        draft_comment_id = draft_comment.json()["id"]
        assert admin.get(f"{BASE}/patches/{patch_id}").status_code == 200
        admin_draft_comments = admin.get(
            f"{BASE}/patches/{patch_id}/comments"
        )
        assert admin_draft_comments.status_code == 200, admin_draft_comments.text
        assert draft_comment_id in {
            item["id"] for item in admin_draft_comments.json()
        }
        assert admin.get(f"{BASE}/patches/{patch_id}/votes").status_code == 200
        assert admin.post(
            f"{BASE}/admin/moderation/{draft_comment_id}/review",
            json={"decision": "approve"},
        ).status_code == 200

        _set_patch_status(patch_id, "merged")

        patch_comment = commenter.post(
            f"{BASE}/patches/{patch_id}/comments",
            json={"content": "[test:political] Government election politics require review."},
        )
        assert patch_comment.status_code == 201, patch_comment.text
        patch_comment_id = patch_comment.json()["id"]
        assert patch_comment.json()["moderation_status"] == "pending_review"
        assert patch_comment_id not in {
            item["id"]
            for item in patch_author.get(
                f"{BASE}/patches/{patch_id}/comments"
            ).json()
        }
        # The earlier reviewed draft comment becomes visible when the patch does.
        assert patch_author.get(f"{BASE}/patches/{patch_id}").json()["comment_count"] == 1

        approved_comment = admin.post(
            f"{BASE}/admin/moderation/{patch_comment_id}/review",
            json={"decision": "approve"},
        )
        assert approved_comment.status_code == 200, approved_comment.text
        assert patch_author.get(f"{BASE}/patches/{patch_id}").json()["comment_count"] == 2
        public_patch_comment = next(
            item
            for item in patch_author.get(
                f"{BASE}/patches/{patch_id}/comments"
            ).json()
            if item["id"] == patch_comment_id
        )
        assert public_patch_comment["moderation_status"] == "published"

        guild = patch_author.post(
            f"{BASE}/guilds",
            json={"name": f"Review Guild {uuid4().hex[:8]}", "description": "Test"},
        )
        assert guild.status_code == 200, guild.text
        guild_id = guild.json()["id"]
        joined = guild_member.post(f"{BASE}/guilds/{guild_id}/join")
        assert joined.status_code == 200, joined.text
        requests = patch_author.get(f"{BASE}/guilds/{guild_id}/requests")
        request_id = next(
            item["id"]
            for item in requests.json()
            if item["user_id"] == guild_member_user["id"]
        )
        assert patch_author.post(
            f"{BASE}/guilds/{guild_id}/requests/{request_id}/approve"
        ).status_code == 200

        discussion = patch_author.post(
            f"{BASE}/guilds/{guild_id}/discussions",
            json={
                "title": "[test:political] Government election topic",
                "content": "[test:political] This internal discussion also waits for review.",
            },
        )
        assert discussion.status_code == 200, discussion.text
        discussion_id = discussion.json()["id"]
        assert discussion.json()["moderation_status"] == "pending_review"
        hidden_guild_delete = guild_member.delete(
            f"{BASE}/guilds/{guild_id}/discussions/{discussion_id}"
        )
        assert hidden_guild_delete.status_code == 404
        assert discussion_id not in {
            item["id"]
            for item in guild_member.get(
                f"{BASE}/guilds/{guild_id}/discussions"
            ).json()
        }

        approved_discussion = admin.post(
            f"{BASE}/admin/moderation/{discussion_id}/review",
            json={"decision": "approve"},
        )
        assert approved_discussion.status_code == 200, approved_discussion.text
        member_discussions = guild_member.get(
            f"{BASE}/guilds/{guild_id}/discussions"
        ).json()
        assert discussion_id in {item["id"] for item in member_discussions}
    finally:
        patch_author.close()
        commenter.close()
        guild_member.close()
        admin.close()


def test_committed_review_effects_reconcile_without_duplicate_notifications():
    author, author_user = _account("delivery-author")
    follower, _ = _account("delivery-follower")
    commenter, _ = _account("delivery-commenter")
    admin, admin_user = _account("delivery-admin")
    _set_role(admin_user["id"], "moderator")

    try:
        followed = follower.put(f"{BASE}/users/{author_user['id']}/follow")
        assert followed.status_code == 200, followed.text

        pending_post = author.post(
            f"{BASE}/posts",
            json={
                "title": "Government policy recovery",
                "content": "A held post whose delivery is recovered.",
            },
        )
        assert pending_post.status_code == 201, pending_post.text
        post_id = pending_post.json()["id"]
        _stage_approval_without_delivery(post_id, admin_user["id"])
        _run_delivery_reconciliation_twice()
        _clear_delivery_marker(post_id)
        _run_delivery_reconciliation_twice()

        state = _content_delivery_state(post_id)
        assert state["moderation_effects_completed_at"] is not None
        author_items = author.get(f"{BASE}/notifications").json()["items"]
        assert sum(
            item["type"] == "moderation_approved"
            and item["link"] == f"/posts/{post_id}"
            for item in author_items
        ) == 1
        follower_items = follower.get(f"{BASE}/notifications").json()["items"]
        assert sum(
            item["type"] == "following_post"
            and item["link"] == f"/posts/{post_id}"
            for item in follower_items
        ) == 1

        root = author.post(
            f"{BASE}/posts",
            json={"title": "Reply recovery root", "content": "Public root."},
        )
        assert root.status_code == 201, root.text
        root_id = root.json()["id"]
        held_comment = commenter.post(
            f"{BASE}/posts/{root_id}/comments",
            json={"content": "[test:political] Government election reply held for review."},
        )
        assert held_comment.status_code == 201, held_comment.text
        comment_id = held_comment.json()["id"]
        _stage_approval_without_delivery(comment_id, admin_user["id"])
        _run_delivery_reconciliation_twice()
        _clear_delivery_marker(comment_id)
        _run_delivery_reconciliation_twice()

        reply_items = author.get(f"{BASE}/notifications").json()["items"]
        assert sum(
            item["type"] == "reply"
            and item["link"] == f"/posts/{root_id}#{comment_id}"
            for item in reply_items
        ) == 1
    finally:
        author.close()
        follower.close()
        commenter.close()
        admin.close()
