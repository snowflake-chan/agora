"""Integration coverage for guild membership and moderation boundaries."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import httpx
import pytest


pytestmark = pytest.mark.usefixtures("server")
BASE = "http://localhost:8000/api/v1"


def _register(client: httpx.Client, *, email: str | None = None) -> tuple[dict, dict[str, str]]:
    suffix = uuid4().hex[:10]
    response = client.post(
        f"{BASE}/auth/register",
        json={
            "email": email or f"guild-{suffix}@example.com",
            "username": f"guild-{suffix}",
            "password": "testpass123",
        },
    )
    assert response.status_code == 200, response.text
    cookie = response.cookies.get("Authorization")
    return response.json(), {"Cookie": f"Authorization={cookie}"}


def test_pending_guild_members_cannot_read_or_publish_internal_discussions():
    with httpx.Client() as client:
        president, president_headers = _register(client)
        guild_response = client.post(
            f"{BASE}/guilds",
            headers=president_headers,
            json={"name": f"Guild {uuid4().hex[:8]}", "description": "Test guild"},
        )
        assert guild_response.status_code == 200, guild_response.text
        guild_id = guild_response.json()["id"]

        member, member_headers = _register(client)
        join = client.post(
            f"{BASE}/guilds/{guild_id}/join",
            headers=member_headers,
        )
        assert join.status_code == 200
        assert join.json()["status"] == "pending"

        duplicate = client.post(
            f"{BASE}/guilds/{guild_id}/join",
            headers=member_headers,
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["detail"] == "GUILD_REQUEST_PENDING"

        membership = client.get(
            f"{BASE}/guilds/{guild_id}/membership",
            headers=member_headers,
        )
        assert membership.status_code == 200
        assert membership.json()["status"] == "pending"

        private_read = client.get(
            f"{BASE}/guilds/{guild_id}/discussions",
            headers=member_headers,
        )
        assert private_read.status_code == 403
        assert private_read.json()["detail"] == "GUILD_MEMBERSHIP_REQUIRED"

        private_write = client.post(
            f"{BASE}/guilds/{guild_id}/discussions",
            headers=member_headers,
            json={"title": "Pending", "content": "Must not be published"},
        )
        assert private_write.status_code == 403

        requests = client.get(
            f"{BASE}/guilds/{guild_id}/requests",
            headers=president_headers,
        )
        assert requests.status_code == 200
        request = next(item for item in requests.json() if item["user_id"] == member["id"])

        approved = client.post(
            f"{BASE}/guilds/{guild_id}/requests/{request['id']}/approve",
            headers=president_headers,
        )
        assert approved.status_code == 200

        discussion = client.post(
            f"{BASE}/guilds/{guild_id}/discussions",
            headers=member_headers,
            json={"title": "Approved", "content": "Visible to guild members"},
        )
        assert discussion.status_code == 200, discussion.text

        with httpx.Client() as anonymous:
            public_activity = anonymous.get(
                f"{BASE}/users/{member['id']}/content"
            )
        assert public_activity.status_code == 200
        assert discussion.json()["id"] not in {
            item["id"] for item in public_activity.json()
        }

        visible = client.get(
            f"{BASE}/guilds/{guild_id}/discussions",
            headers=member_headers,
        )
        assert visible.status_code == 200
        assert [item["title"] for item in visible.json()] == ["Approved"]


def test_admin_bootstrap_role_boundaries_bans_and_reports():
    with httpx.Client() as client:
        admin, admin_headers = _register(client, email="admin-test@example.com")
        bootstrap = client.post(
            f"{BASE}/admin/seed-super-admin",
            headers=admin_headers,
        )
        assert bootstrap.status_code == 200, bootstrap.text

        invalid_level_names = client.put(
            f"{BASE}/admin/level-names",
            headers=admin_headers,
            json={"1": "Only one level"},
        )
        assert invalid_level_names.status_code == 422
        assert invalid_level_names.json()["detail"] == "INVALID_LEVEL_NAMES"
        valid_level_names = client.put(
            f"{BASE}/admin/level-names",
            headers=admin_headers,
            json={str(index): f"Level {index}" for index in range(1, 6)},
        )
        assert valid_level_names.status_code == 200

        target, target_headers = _register(client)
        moderator, moderator_headers = _register(client)

        promote = client.post(
            f"{BASE}/admin/users/{moderator['id']}/role?role=moderator",
            headers=admin_headers,
        )
        assert promote.status_code == 200

        moderator_reports = client.get(
            f"{BASE}/admin/reports",
            headers=moderator_headers,
        )
        assert moderator_reports.status_code == 200
        moderator_users = client.get(
            f"{BASE}/admin/users",
            headers=moderator_headers,
        )
        assert moderator_users.status_code == 403

        mute = client.post(
            f"{BASE}/admin/users/{target['id']}/ban?hours=1&type=mute_post",
            headers=admin_headers,
        )
        assert mute.status_code == 200

        blocked_post = client.post(
            f"{BASE}/posts",
            headers=target_headers,
            json={"title": "Blocked", "content": "This should not publish"},
        )
        assert blocked_post.status_code == 403
        assert blocked_post.json()["detail"] == "POSTING_RESTRICTED"

        unban = client.post(
            f"{BASE}/admin/users/{target['id']}/unban?type=mute_post",
            headers=admin_headers,
        )
        assert unban.status_code == 200
        post = client.post(
            f"{BASE}/posts",
            headers=target_headers,
            json={"title": "Allowed", "content": "Published after unban"},
        )
        assert post.status_code == 201, post.text

        self_report = client.post(
            f"{BASE}/admin/reports",
            headers=target_headers,
            json={"content_id": post.json()["id"], "reason": "My own post"},
        )
        assert self_report.status_code == 403
        assert self_report.json()["detail"] == "REPORT_OWN_TARGET_FORBIDDEN"

        missing_report_target = client.post(
            f"{BASE}/admin/reports",
            headers=moderator_headers,
            json={"reason": "Missing target"},
        )
        assert missing_report_target.status_code == 422
        assert missing_report_target.json()["detail"] == "REPORT_TARGET_REQUIRED"

        ambiguous_report_target = client.post(
            f"{BASE}/admin/reports",
            headers=moderator_headers,
            json={
                "content_id": post.json()["id"],
                "patch_id": str(uuid4()),
                "reason": "Ambiguous target",
            },
        )
        assert ambiguous_report_target.status_code == 422
        assert ambiguous_report_target.json()["detail"] == "REPORT_TARGET_AMBIGUOUS"

        first_report = client.post(
            f"{BASE}/admin/reports",
            headers=moderator_headers,
            json={"content_id": post.json()["id"], "reason": "Review this"},
        )
        assert first_report.status_code == 200
        duplicate_report = client.post(
            f"{BASE}/admin/reports",
            headers=moderator_headers,
            json={"content_id": post.json()["id"], "reason": "Duplicate"},
        )
        assert duplicate_report.status_code == 409
        assert duplicate_report.json()["detail"] == "REPORT_ALREADY_EXISTS"

        patch = client.post(
            f"{BASE}/patches",
            headers=target_headers,
            json={
                "title": f"Reported patch {uuid4().hex[:8]}",
                "content": "Patch content that should be reviewable",
                "pr_number": 900_000 + int(uuid4().hex[:5], 16),
            },
        )
        assert patch.status_code == 201, patch.text
        patch_id = patch.json()["id"]

        self_patch_report = client.post(
            f"{BASE}/admin/reports",
            headers=target_headers,
            json={"patch_id": patch_id, "reason": "My own patch"},
        )
        assert self_patch_report.status_code == 403
        assert self_patch_report.json()["detail"] == "REPORT_OWN_TARGET_FORBIDDEN"

        patch_mute = client.post(
            f"{BASE}/admin/users/{target['id']}/ban?hours=1&type=mute_patch",
            headers=admin_headers,
        )
        assert patch_mute.status_code == 200
        blocked_patch_comment = client.post(
            f"{BASE}/patches/{patch_id}/comments",
            headers=target_headers,
            json={"content": "This should be blocked while patch-muted"},
        )
        assert blocked_patch_comment.status_code == 403
        assert blocked_patch_comment.json()["detail"] == "PATCHING_RESTRICTED"
        patch_unban = client.post(
            f"{BASE}/admin/users/{target['id']}/unban?type=mute_patch",
            headers=admin_headers,
        )
        assert patch_unban.status_code == 200

        patch_comment = client.post(
            f"{BASE}/patches/{patch_id}/comments",
            headers=target_headers,
            json={"content": "A reportable patch comment"},
        )
        assert patch_comment.status_code == 201, patch_comment.text
        patch_comment_report = client.post(
            f"{BASE}/admin/reports",
            headers=moderator_headers,
            json={
                "content_id": patch_comment.json()["id"],
                "reason": "Review this patch comment",
            },
        )
        assert patch_comment_report.status_code == 200

        patch_report = client.post(
            f"{BASE}/admin/reports",
            headers=moderator_headers,
            json={"patch_id": patch_id, "reason": "Review this patch"},
        )
        assert patch_report.status_code == 200, patch_report.text
        duplicate_patch_report = client.post(
            f"{BASE}/admin/reports",
            headers=moderator_headers,
            json={"patch_id": patch_id, "reason": "Duplicate patch report"},
        )
        assert duplicate_patch_report.status_code == 409
        assert duplicate_patch_report.json()["detail"] == "REPORT_ALREADY_EXISTS"

        report_list = client.get(
            f"{BASE}/admin/reports",
            headers=admin_headers,
        )
        assert report_list.status_code == 200
        listed_patch_report = next(
            item for item in report_list.json() if item["id"] == patch_report.json()["id"]
        )
        assert listed_patch_report["target_type"] == "patch"
        assert listed_patch_report["patch_id"] == patch_id
        assert listed_patch_report["content_title"] == patch.json()["title"]
        assert listed_patch_report["target_href"] == f"/patches/{patch_id}"
        listed_comment_report = next(
            item
            for item in report_list.json()
            if item["id"] == patch_comment_report.json()["id"]
        )
        assert listed_comment_report["target_href"] == (
            f"/patches/{patch_id}#{patch_comment.json()['id']}"
        )
        listed_post_report = next(
            item for item in report_list.json() if item["id"] == first_report.json()["id"]
        )
        assert listed_post_report["target_href"] == f"/posts/{post.json()['id']}"

        resolve_patch_report = client.post(
            f"{BASE}/admin/reports/{patch_report.json()['id']}/resolve",
            headers=moderator_headers,
            params={"action": "resolved"},
        )
        assert resolve_patch_report.status_code == 200

        second_reporter, second_reporter_headers = _register(client)
        second_report = client.post(
            f"{BASE}/admin/reports",
            headers=second_reporter_headers,
            json={"content_id": post.json()["id"], "reason": "Second report"},
        )
        assert second_report.status_code == 200

        moderator_delete = client.post(
            f"{BASE}/admin/reports/{first_report.json()['id']}/resolve",
            headers=moderator_headers,
            params={"action": "delete_post"},
        )
        assert moderator_delete.status_code == 403

        admin_delete = client.post(
            f"{BASE}/admin/reports/{first_report.json()['id']}/resolve",
            headers=admin_headers,
            params={"action": "delete_post"},
        )
        assert admin_delete.status_code == 200, admin_delete.text
        assert admin_delete.json()["also_resolved"] == 1

        duplicate_resolve = client.post(
            f"{BASE}/admin/reports/{first_report.json()['id']}/resolve",
            headers=admin_headers,
            params={"action": "resolved"},
        )
        assert duplicate_resolve.status_code == 409
        assert duplicate_resolve.json()["detail"] == "REPORT_ALREADY_RESOLVED"

        concurrent_post = client.post(
            f"{BASE}/posts",
            headers=target_headers,
            json={"title": "Concurrent review", "content": "Resolve once"},
        )
        assert concurrent_post.status_code == 201
        concurrent_report_ids = []
        for headers in (moderator_headers, second_reporter_headers):
            report = client.post(
                f"{BASE}/admin/reports",
                headers=headers,
                json={
                    "content_id": concurrent_post.json()["id"],
                    "reason": "Concurrent moderation",
                },
            )
            assert report.status_code == 200
            concurrent_report_ids.append(report.json()["id"])

        def resolve_concurrently(report_id: str) -> httpx.Response:
            with httpx.Client(timeout=10) as concurrent_client:
                return concurrent_client.post(
                    f"{BASE}/admin/reports/{report_id}/resolve",
                    headers=admin_headers,
                    params={"action": "resolved"},
                )

        with ThreadPoolExecutor(max_workers=2) as pool:
            concurrent_results = list(pool.map(resolve_concurrently, concurrent_report_ids))
        assert sorted(result.status_code for result in concurrent_results) == [200, 409]
        successful_resolve = next(result for result in concurrent_results if result.status_code == 200)
        assert successful_resolve.json()["also_resolved"] == 1

        reports_after_delete = client.get(
            f"{BASE}/admin/reports",
            headers=admin_headers,
        )
        assert reports_after_delete.status_code == 200
        deleted_target_reports = [
            item
            for item in reports_after_delete.json()
            if item["id"] in (first_report.json()["id"], second_report.json()["id"])
        ]
        assert len(deleted_target_reports) == 2
        assert {item["status"] for item in deleted_target_reports} == {"resolved"}
        assert {item["content_id"] for item in deleted_target_reports} == {None}

        target_guild = client.post(
            f"{BASE}/guilds",
            headers=target_headers,
            json={"name": f"Restricted Guild {uuid4().hex[:8]}"},
        )
        assert target_guild.status_code == 200
        target_guild_id = target_guild.json()["id"]
        applicant, applicant_headers = _register(client)
        assert client.post(
            f"{BASE}/guilds/{target_guild_id}/join",
            headers=applicant_headers,
        ).status_code == 200
        requests = client.get(
            f"{BASE}/guilds/{target_guild_id}/requests",
            headers=target_headers,
        )
        applicant_request_id = next(
            item["id"] for item in requests.json() if item["user_id"] == applicant["id"]
        )

        guild_discussion = client.post(
            f"{BASE}/guilds/{target_guild_id}/discussions",
            headers=target_headers,
            json={"title": "Moderation target", "content": "Private discussion"},
        )
        assert guild_discussion.status_code == 200
        moderator_discussions = client.get(
            f"{BASE}/guilds/{target_guild_id}/discussions",
            headers=moderator_headers,
        )
        assert moderator_discussions.status_code == 200
        assert guild_discussion.json()["id"] in {
            item["id"] for item in moderator_discussions.json()
        }

        global_ban = client.post(
            f"{BASE}/admin/users/{target['id']}/ban?hours=1&type=ban_user",
            headers=admin_headers,
        )
        assert global_ban.status_code == 200

        blocked_guild_update = client.patch(
            f"{BASE}/guilds/{target_guild_id}",
            headers=target_headers,
            json={"description": "Must not change"},
        )
        assert blocked_guild_update.status_code == 403
        assert blocked_guild_update.json()["detail"] == "ACCOUNT_BANNED"
        blocked_guild_approve = client.post(
            f"{BASE}/guilds/{target_guild_id}/requests/{applicant_request_id}/approve",
            headers=target_headers,
        )
        assert blocked_guild_approve.status_code == 403
        assert blocked_guild_approve.json()["detail"] == "ACCOUNT_BANNED"
        blocked_guild_delete = client.delete(
            f"{BASE}/guilds/{target_guild_id}",
            headers=target_headers,
        )
        assert blocked_guild_delete.status_code == 403

        blocked_like = client.put(
            f"{BASE}/posts/{post.json()['id']}/like",
            headers=target_headers,
        )
        assert blocked_like.status_code == 403
        assert blocked_like.json()["detail"] == "ACCOUNT_BANNED"

        blocked_follow = client.put(
            f"{BASE}/users/{moderator['id']}/follow",
            headers=target_headers,
        )
        assert blocked_follow.status_code == 403

        blocked_report = client.post(
            f"{BASE}/admin/reports",
            headers=target_headers,
            json={"content_id": post.json()["id"], "reason": "Blocked report"},
        )
        assert blocked_report.status_code == 403


def test_guild_role_cap_and_draft_visibility():
    with httpx.Client() as client:
        president, president_headers = _register(client)
        guild_name = f"Guild {uuid4().hex[:8]}"
        guild_response = client.post(
            f"{BASE}/guilds",
            headers=president_headers,
            json={
                "name": f"  {guild_name}  ",
                "logo": "   ",
                "description": "  trimmed description  ",
            },
        )
        assert guild_response.status_code == 200, guild_response.text
        guild = guild_response.json()
        guild_id = guild["id"]
        assert guild["name"] == guild_name
        assert guild["logo"] is None
        assert guild["description"] == "trimmed description"

        racer, racer_headers = _register(client)

        def join_concurrently(_: int) -> httpx.Response:
            with httpx.Client(timeout=10) as concurrent_client:
                return concurrent_client.post(
                    f"{BASE}/guilds/{guild_id}/join",
                    headers=racer_headers,
                )

        with ThreadPoolExecutor(max_workers=2) as pool:
            join_results = list(pool.map(join_concurrently, range(2)))
        assert sorted(result.status_code for result in join_results) == [200, 409]
        duplicate_join = next(
            result for result in join_results if result.status_code == 409
        )
        assert duplicate_join.json()["detail"] == "GUILD_REQUEST_PENDING"

        pending, pending_headers = _register(client)
        join = client.post(f"{BASE}/guilds/{guild_id}/join", headers=pending_headers)
        assert join.status_code == 200
        bypass = client.patch(
            f"{BASE}/guilds/{guild_id}/members/{pending['id']}?role=vice_president",
            headers=president_headers,
        )
        assert bypass.status_code == 404

        requests = client.get(f"{BASE}/guilds/{guild_id}/requests", headers=president_headers)
        assert requests.status_code == 200
        request_id = next(item["id"] for item in requests.json() if item["user_id"] == pending["id"])
        approved = client.post(
            f"{BASE}/guilds/{guild_id}/requests/{request_id}/approve",
            headers=president_headers,
        )
        assert approved.status_code == 200

        promoted = client.patch(
            f"{BASE}/guilds/{guild_id}/members/{pending['id']}?role=vice_president",
            headers=president_headers,
        )
        assert promoted.status_code == 200

        discussion = client.post(
            f"{BASE}/guilds/{guild_id}/discussions",
            headers=pending_headers,
            json={"title": "   ", "content": "  trimmed discussion  "},
        )
        assert discussion.status_code == 200
        assert discussion.json()["title"] is None
        assert discussion.json()["content"] == "trimmed discussion"

        second, second_headers = _register(client)
        assert client.post(f"{BASE}/guilds/{guild_id}/join", headers=second_headers).status_code == 200
        requests = client.get(f"{BASE}/guilds/{guild_id}/requests", headers=president_headers)
        second_request_id = next(item["id"] for item in requests.json() if item["user_id"] == second["id"])
        assert client.post(
            f"{BASE}/guilds/{guild_id}/requests/{second_request_id}/approve",
            headers=president_headers,
        ).status_code == 200
        over_cap = client.patch(
            f"{BASE}/guilds/{guild_id}/members/{second['id']}?role=vice_president",
            headers=president_headers,
        )
        assert over_cap.status_code == 409
        assert over_cap.json()["detail"] == "GUILD_VP_LIMIT_REACHED"

        draft = client.post(
            f"{BASE}/patches",
            headers=pending_headers,
            json={
                "title": f"Private draft {uuid4().hex[:8]}",
                "content": "Draft should only be visible to its author.",
                "pr_number": 910_000 + int(uuid4().hex[:5], 16),
            },
        )
        assert draft.status_code == 201, draft.text
        draft_id = draft.json()["id"]

        public_patches = client.get(f"{BASE}/guilds/{guild_id}/patches")
        assert public_patches.status_code == 200
        assert draft_id not in {item["id"] for item in public_patches.json()}
        author_patches = client.get(
            f"{BASE}/guilds/{guild_id}/patches",
            headers=pending_headers,
        )
        assert author_patches.status_code == 200
        assert draft_id in {item["id"] for item in author_patches.json()}

        missing_guild = client.get(f"{BASE}/guilds/{uuid4()}/patches")
        assert missing_guild.status_code == 404
        assert missing_guild.json()["detail"] == "GUILD_NOT_FOUND"


def test_concurrent_guild_name_conflict_is_409():
    with httpx.Client() as client:
        _, first_headers = _register(client)
        _, second_headers = _register(client)
        guild_name = f"Concurrent Guild {uuid4().hex[:8]}"

        def create(headers: dict[str, str]) -> httpx.Response:
            with httpx.Client(timeout=10) as concurrent_client:
                return concurrent_client.post(
                    f"{BASE}/guilds",
                    headers=headers,
                    json={"name": guild_name},
                )

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(create, (first_headers, second_headers)))

        assert sorted(result.status_code for result in results) == [200, 409]
        conflict = next(result for result in results if result.status_code == 409)
        assert conflict.json()["detail"] == "GUILD_NAME_TAKEN"
