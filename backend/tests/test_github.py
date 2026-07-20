import httpx
import pytest

from app.config import settings
from app.patches.github import GitHubPullRequestError, get_pull_request


@pytest.mark.asyncio
async def test_get_pull_request_uses_configured_repo(monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_REPO", "example/agora")
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "test-token")
    async_client = httpx.AsyncClient

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.github.com/repos/example/agora/pulls/17"
        assert request.headers["Authorization"] == "Bearer test-token"
        return httpx.Response(
            200,
            json={"number": 17, "state": "open", "draft": False},
        )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: async_client(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )

    pull_request = await get_pull_request(17)
    assert pull_request["number"] == 17


@pytest.mark.asyncio
async def test_get_pull_request_reports_missing_pr(monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_REPO", "example/agora")
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "")
    async_client = httpx.AsyncClient

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: async_client(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )

    with pytest.raises(GitHubPullRequestError, match="PULL_REQUEST_NOT_FOUND"):
        await get_pull_request(999)
