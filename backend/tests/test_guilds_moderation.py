"""Integration coverage for guild membership and moderation boundaries."""

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

        missing_report_target = client.post(
            f"{BASE}/admin/reports",
            headers=moderator_headers,
            params={"reason": "Missing target"},
        )
        assert missing_report_target.status_code == 422
        assert missing_report_target.json()["detail"] == "REPORT_TARGET_REQUIRED"

        ambiguous_report_target = client.post(
            f"{BASE}/admin/reports",
            headers=moderator_headers,
            params={
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
            params={"content_id": post.json()["id"], "reason": "Review this"},
        )
        assert first_report.status_code == 200
        duplicate_report = client.post(
            f"{BASE}/admin/reports",
            headers=moderator_headers,
            params={"content_id": post.json()["id"], "reason": "Duplicate"},
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

        patch_report = client.post(
            f"{BASE}/admin/reports",
            headers=moderator_headers,
            params={"patch_id": patch_id, "reason": "Review this patch"},
        )
        assert patch_report.status_code == 200, patch_report.text
        duplicate_patch_report = client.post(
            f"{BASE}/admin/reports",
            headers=moderator_headers,
            params={"patch_id": patch_id, "reason": "Duplicate patch report"},
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
            params={"content_id": post.json()["id"], "reason": "Second report"},
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

        global_ban = client.post(
            f"{BASE}/admin/users/{target['id']}/ban?hours=1&type=ban_user",
            headers=admin_headers,
        )
        assert global_ban.status_code == 200

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
            params={"content_id": post.json()["id"], "reason": "Blocked report"},
        )
        assert blocked_report.status_code == 403
