"""Integration tests for native post poll creation, reads, and voting."""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest

from app.schemas.post import poll_option_digest


pytestmark = pytest.mark.usefixtures("server")

BASE = "http://localhost:8000"


def _account(prefix: str) -> tuple[httpx.Client, dict]:
    client = httpx.Client()
    suffix = uuid4().hex[:10]
    password = "testpass123"
    registered = client.post(
        f"{BASE}/api/v1/auth/register",
        json={
            "email": f"{prefix}-{suffix}@test.dev",
            "username": f"{prefix}-{suffix}",
            "password": password,
        },
    )
    assert registered.status_code == 200, registered.text
    logged_in = client.post(
        f"{BASE}/api/v1/auth/login",
        json={"email": registered.json()["email"], "password": password},
    )
    assert logged_in.status_code == 200, logged_in.text
    token = logged_in.cookies.get("Authorization")
    assert token
    client.headers["Cookie"] = f"Authorization={token}"
    return client, registered.json()


def _create_poll_post(
    client: httpx.Client,
    *,
    question: str = "Which option should we choose?",
    options: list[str] | None = None,
    duration_hours: int = 24,
) -> dict:
    response = client.post(
        f"{BASE}/api/v1/posts",
        json={
            "title": "Opinion poll",
            "content": "Please vote on this choice.",
            "poll": {
                "question": question,
                "options": options or ["First option", "Second option"],
                "duration_hours": duration_hours,
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _database_url() -> str:
    return os.environ["DATABASE_URL"].replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )


def _close_poll(poll_id: str) -> None:
    async def close() -> None:
        connection = await asyncpg.connect(_database_url())
        try:
            await connection.execute(
                """
                UPDATE post_poll
                SET created_at = clock_timestamp() - INTERVAL '2 hours',
                    closes_at = clock_timestamp() - INTERVAL '1 hour'
                WHERE id = $1
                """,
                UUID(poll_id),
            )
        finally:
            await connection.close()

    asyncio.run(close())


def _ban_user(user_id: str) -> None:
    async def ban() -> None:
        connection = await asyncpg.connect(_database_url())
        try:
            await connection.execute(
                """
                INSERT INTO ban_record
                    (id, target_user_id, type, reason, duration_hours,
                     expires_at, created_at, is_active)
                VALUES ($1, $2, 'ban_user', 'poll test', NULL,
                        NULL, clock_timestamp(), TRUE)
                """,
                uuid4(),
                UUID(user_id),
            )
        finally:
            await connection.close()

    asyncio.run(ban())


def test_post_poll_validation_rejects_invalid_shapes():
    client, _ = _account("poll-validation")
    try:
        common = {
            "title": "Validation poll",
            "content": "Poll validation coverage.",
        }
        invalid_polls = [
            {"question": "tiny", "options": ["One", "Two"], "duration_hours": 24},
            {"question": "Valid question", "options": ["Only one"], "duration_hours": 24},
            {
                "question": "Valid question",
                "options": ["  Same answer ", "same   answer"],
                "duration_hours": 24,
            },
            {
                "question": "Valid question",
                "options": ["", "Second answer"],
                "duration_hours": 24,
            },
            {
                "question": "Valid question",
                "options": ["x" * 81, "Second answer"],
                "duration_hours": 24,
            },
            {
                "question": "Valid question",
                "options": [str(index) for index in range(7)],
                "duration_hours": 24,
            },
            {
                "question": "Valid question",
                "options": ["One", "Two"],
                "duration_hours": 23,
            },
            {
                "question": "Valid question",
                "options": ["One", "Two"],
                "duration_hours": 721,
            },
        ]
        for poll in invalid_polls:
            response = client.post(f"{BASE}/api/v1/posts", json={**common, "poll": poll})
            assert response.status_code == 422, response.text

        expansion = "\ufdfa" * 80
        normalized_expansion = client.post(
            f"{BASE}/api/v1/posts",
            json={
                **common,
                "poll": {
                    "question": "Can normalized options be stored safely?",
                    "options": [expansion, "Other"],
                    "duration_hours": 24,
                },
            },
        )
        assert normalized_expansion.status_code == 201, normalized_expansion.text
    finally:
        client.close()


def test_poll_creation_anonymous_read_and_feed_contract():
    author, author_data = _account("poll-author")
    try:
        created = _create_poll_post(
            author,
            question="  Which direction should this take?  ",
            options=["  First   choice ", "Second choice"],
            duration_hours=24,
        )
        poll = created["poll"]
        assert poll["question"] == "Which direction should this take?"
        assert [option["text"] for option in poll["options"]] == [
            "First choice",
            "Second choice",
        ]
        assert poll["total_votes"] == 0
        assert poll["is_closed"] is False
        assert poll["selected_option_id"] is None
        closes_at = datetime.fromisoformat(poll["closes_at"])
        remaining = closes_at - datetime.now(timezone.utc)
        assert timedelta(hours=23, minutes=59) < remaining <= timedelta(hours=24)

        with httpx.Client() as anonymous:
            detail = anonymous.get(f"{BASE}/api/v1/posts/{created['id']}")
            assert detail.status_code == 200, detail.text
            assert detail.json()["poll"]["id"] == poll["id"]
            assert detail.json()["poll"]["selected_option_id"] is None

            listed = anonymous.get(f"{BASE}/api/v1/posts", params={"page_size": 100})
            assert listed.status_code == 200, listed.text
            list_item = next(item for item in listed.json() if item["id"] == created["id"])
            assert list_item["poll"]["total_votes"] == 0

            feed = anonymous.get(
                f"{BASE}/api/v1/posts/-/feed",
                params={"mode": "latest", "page_size": 100},
            )
            assert feed.status_code == 200, feed.text
            feed_item = next(item for item in feed.json() if item["id"] == created["id"])
            assert feed_item["type"] == "post"
            assert feed_item["poll"]["question"] == poll["question"]
            assert feed_item["poll"]["selected_option_id"] is None

        profile = author.get(f"{BASE}/api/v1/users/{author_data['id']}/posts")
        assert profile.status_code == 200, profile.text
        assert next(item for item in profile.json() if item["id"] == created["id"])["poll"]
    finally:
        author.close()


def test_vote_is_idempotent_mutable_and_scoped_to_its_poll():
    author, _ = _account("poll-vote-author")
    voter, _ = _account("poll-voter")
    try:
        first_post = _create_poll_post(author)
        second_post = _create_poll_post(
            author,
            question="Which release should we publish?",
            options=["Release A", "Release B"],
        )
        first_options = first_post["poll"]["options"]
        first_option_id = first_options[0]["id"]
        second_option_id = second_post["poll"]["options"][0]["id"]

        with httpx.Client() as anonymous:
            unauthenticated = anonymous.put(
                f"{BASE}/api/v1/posts/{first_post['id']}/poll/vote",
                json={"option_id": first_option_id},
            )
            assert unauthenticated.status_code == 401

        first_vote = voter.put(
            f"{BASE}/api/v1/posts/{first_post['id']}/poll/vote",
            json={"option_id": first_option_id},
        )
        assert first_vote.status_code == 200, first_vote.text
        same_vote = voter.put(
            f"{BASE}/api/v1/posts/{first_post['id']}/poll/vote",
            json={"option_id": first_option_id},
        )
        assert same_vote.status_code == 200, same_vote.text
        assert same_vote.json()["total_votes"] == 1
        assert same_vote.json()["selected_option_id"] == first_option_id

        changed = voter.put(
            f"{BASE}/api/v1/posts/{first_post['id']}/poll/vote",
            json={"option_id": first_options[1]["id"]},
        )
        assert changed.status_code == 200, changed.text
        assert changed.json()["total_votes"] == 1
        assert changed.json()["selected_option_id"] == first_options[1]["id"]
        assert [option["vote_count"] for option in changed.json()["options"]] == [0, 1]

        feed = voter.get(
            f"{BASE}/api/v1/posts/-/feed",
            params={"mode": "latest", "page_size": 100},
        )
        feed_item = next(item for item in feed.json() if item["id"] == first_post["id"])
        assert feed_item["poll"]["selected_option_id"] == first_options[1]["id"]

        wrong_option = voter.put(
            f"{BASE}/api/v1/posts/{first_post['id']}/poll/vote",
            json={"option_id": second_option_id},
        )
        assert wrong_option.status_code == 404
        assert wrong_option.json()["detail"] == "POLL_OPTION_NOT_FOUND"

        no_poll = author.post(
            f"{BASE}/api/v1/posts",
            json={"title": "Plain post", "content": "No poll here."},
        )
        assert no_poll.status_code == 201
        missing = voter.put(
            f"{BASE}/api/v1/posts/{no_poll.json()['id']}/poll/vote",
            json={"option_id": first_option_id},
        )
        assert missing.status_code == 404
    finally:
        author.close()
        voter.close()


def test_concurrent_votes_preserve_one_choice_per_user():
    author, _ = _account("poll-race-author")
    voter, _ = _account("poll-race-voter")
    try:
        created = _create_poll_post(author)
        url = f"{BASE}/api/v1/posts/{created['id']}/poll/vote"
        option_ids = [option["id"] for option in created["poll"]["options"]]
        cookie = voter.headers["Cookie"]

        def cast(option_id: str) -> httpx.Response:
            return httpx.put(
                url,
                json={"option_id": option_id},
                headers={"Cookie": cookie},
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(cast, option_ids))
        assert all(result.status_code == 200 for result in results)

        final = voter.get(f"{BASE}/api/v1/posts/{created['id']}")
        poll = final.json()["poll"]
        assert poll["total_votes"] == 1
        assert poll["selected_option_id"] in option_ids
        assert sum(option["vote_count"] for option in poll["options"]) == 1
    finally:
        author.close()
        voter.close()


def test_closed_poll_rejects_votes_and_reports_closed_state():
    author, _ = _account("poll-close-author")
    voter, _ = _account("poll-close-voter")
    try:
        created = _create_poll_post(author)
        _close_poll(created["poll"]["id"])
        blocked = voter.put(
            f"{BASE}/api/v1/posts/{created['id']}/poll/vote",
            json={"option_id": created["poll"]["options"][0]["id"]},
        )
        assert blocked.status_code == 409
        assert blocked.json()["detail"] == "POLL_CLOSED"

        detail = voter.get(f"{BASE}/api/v1/posts/{created['id']}")
        assert detail.status_code == 200
        assert detail.json()["poll"]["is_closed"] is True
    finally:
        author.close()
        voter.close()


def test_banned_user_cannot_vote():
    author, _ = _account("poll-ban-author")
    voter, voter_data = _account("poll-ban-voter")
    try:
        created = _create_poll_post(author)
        _ban_user(voter_data["id"])
        response = voter.put(
            f"{BASE}/api/v1/posts/{created['id']}/poll/vote",
            json={"option_id": created["poll"]["options"][0]["id"]},
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "ACCOUNT_BANNED"
    finally:
        author.close()
        voter.close()


def test_poll_database_constraints_prevent_duplicate_polls_and_cross_poll_votes():
    author, author_data = _account("poll-db-author")
    voter, voter_data = _account("poll-db-voter")
    try:
        first_post = _create_poll_post(author)
        second_post = _create_poll_post(
            author,
            question="Which database invariant matters?",
            options=["Foreign keys", "Unique constraints"],
        )
        first_poll = first_post["poll"]
        second_option_id = second_post["poll"]["options"][0]["id"]

        async def assert_constraints() -> None:
            connection = await asyncpg.connect(_database_url())
            try:
                with pytest.raises(asyncpg.UniqueViolationError):
                    await connection.execute(
                        """
                        INSERT INTO post_poll (id, post_id, question, created_at, closes_at)
                        VALUES ($1, $2, $3, clock_timestamp(),
                                clock_timestamp() + INTERVAL '24 hours')
                        """,
                        uuid4(),
                        UUID(first_post["id"]),
                        "A duplicate poll must not be created",
                    )

                with pytest.raises(asyncpg.ForeignKeyViolationError):
                    await connection.execute(
                        """
                        INSERT INTO post_poll_vote
                            (id, poll_id, option_id, user_id, created_at, updated_at)
                        VALUES ($1, $2, $3, $4, clock_timestamp(), clock_timestamp())
                        """,
                        uuid4(),
                        UUID(first_poll["id"]),
                        UUID(second_option_id),
                        UUID(voter_data["id"]),
                    )

                with pytest.raises(asyncpg.UniqueViolationError):
                    await connection.execute(
                        """
                        INSERT INTO post_poll_option
                            (id, poll_id, text, normalized_digest, position)
                        VALUES ($1, $2, $3, $4, 2)
                        """,
                        uuid4(),
                        UUID(first_poll["id"]),
                        "First option",
                        poll_option_digest("First option"),
                    )

                with pytest.raises(asyncpg.CheckViolationError):
                    await connection.execute(
                        "DELETE FROM post_poll_option WHERE id = $1",
                        UUID(first_poll["options"][0]["id"]),
                    )

                with pytest.raises(asyncpg.CheckViolationError):
                    await connection.execute(
                        """
                        UPDATE post_poll_option
                        SET poll_id = $1, position = 2
                        WHERE id = $2
                        """,
                        UUID(second_post["poll"]["id"]),
                        UUID(first_poll["options"][0]["id"]),
                    )
            finally:
                await connection.close()

        asyncio.run(assert_constraints())
    finally:
        author.close()
        voter.close()
