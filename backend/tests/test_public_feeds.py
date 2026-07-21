"""Public syndication exposes only content already visible to everyone."""

from uuid import uuid4
from xml.etree import ElementTree

import httpx
import pytest


pytestmark = pytest.mark.usefixtures("server")
BASE = "http://localhost:8000/api/v1"


def _account() -> httpx.Client:
    client = httpx.Client()
    suffix = uuid4().hex[:10]
    password = "testpass123"
    registered = client.post(
        f"{BASE}/auth/register",
        json={
            "email": f"feed-{suffix}@test.dev",
            "username": f"feed-{suffix}",
            "password": password,
        },
    )
    assert registered.status_code == 200, registered.text
    login = client.post(
        f"{BASE}/auth/login",
        json={"email": registered.json()["email"], "password": password},
    )
    assert login.status_code == 200, login.text
    client.headers["Cookie"] = f"Authorization={login.cookies['Authorization']}"
    return client


def test_public_rss_and_json_feed_hide_private_workflow_states():
    author = _account()
    try:
        public_post = author.post(
            f"{BASE}/posts",
            json={"title": "Public feed marker", "content": "Visible to everyone."},
        )
        assert public_post.status_code == 201, public_post.text

        pending_post = author.post(
            f"{BASE}/posts",
            json={
                "title": "Government election marker",
                "content": "This political discussion must wait for review.",
            },
        )
        assert pending_post.status_code == 201, pending_post.text
        assert pending_post.json()["moderation_status"] == "pending_review"

        draft_patch = author.post(
            f"{BASE}/patches",
            json={
                "title": "Private draft marker",
                "content": "A draft must not enter public feeds.",
                "pr_number": 900_000 + int(uuid4().hex[:5], 16),
            },
        )
        assert draft_patch.status_code == 201, draft_patch.text

        with httpx.Client() as anonymous:
            rss = anonymous.get(f"{BASE}/public/rss.xml")
            assert rss.status_code == 200, rss.text
            assert rss.headers["content-type"].startswith("application/rss+xml")
            root = ElementTree.fromstring(rss.content)
            titles = [item.text for item in root.findall("./channel/item/title")]
            assert "Public feed marker" in titles
            assert "Government election marker" not in titles
            assert "Private draft marker" not in titles

            json_response = anonymous.get(f"{BASE}/public/feed.json")
            assert json_response.status_code == 200, json_response.text
            assert json_response.json()["version"].endswith("/1.1")
            json_titles = [item["title"] for item in json_response.json()["items"]]
            assert "Public feed marker" in json_titles
            assert "Government election marker" not in json_titles
            assert "Private draft marker" not in json_titles
            original_item = next(
                item
                for item in json_response.json()["items"]
                if item["title"] == "Public feed marker"
            )
            assert original_item["id"] == f"post:{public_post.json()['id']}"

            edited = author.patch(
                f"{BASE}/posts/{public_post.json()['id']}",
                json={"content": "Visible with a correction.", "revision_number": 1},
            )
            assert edited.status_code == 200, edited.text
            refreshed_response = anonymous.get(f"{BASE}/public/feed.json")
            refreshed = refreshed_response.json()
            edited_item = next(
                item
                for item in refreshed["items"]
                if item["title"] == "Public feed marker"
            )
            assert edited_item["id"] == original_item["id"]
            assert edited_item["date_modified"] != original_item["date_modified"]

            cached = anonymous.get(
                f"{BASE}/public/feed.json",
                headers={"If-None-Match": refreshed_response.headers["etag"]},
            )
            assert cached.status_code == 304
    finally:
        author.close()
