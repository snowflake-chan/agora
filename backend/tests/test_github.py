import httpx
import pytest

from app.config import settings
from app.patches.github import (
    GitHubMergeUncertainError,
    GitHubPullRequestError,
    get_pull_request,
    merge_pr,
    pull_request_readiness_error,
)


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


@pytest.mark.asyncio
async def test_merge_pr_recovers_when_github_already_merged(monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_REPO", "example/agora")
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "test-token")
    async_client = httpx.AsyncClient

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PUT":
            return httpx.Response(405, json={"message": "Pull Request is not mergeable"})
        return httpx.Response(
            200,
            json={"number": 17, "state": "closed", "merged": True},
        )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: async_client(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )

    assert await merge_pr(17) is False


@pytest.mark.asyncio
async def test_merge_pr_recovers_after_timeout_when_github_merged(monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_REPO", "example/agora")
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "test-token")
    async_client = httpx.AsyncClient

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PUT":
            raise httpx.ReadTimeout("merge response timed out", request=request)
        return httpx.Response(
            200,
            json={"number": 17, "state": "closed", "merged": True},
        )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: async_client(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )

    assert await merge_pr(17) is False


@pytest.mark.asyncio
async def test_merge_pr_marks_unreachable_github_as_uncertain(monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_REPO", "example/agora")
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "test-token")
    async_client = httpx.AsyncClient

    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network unavailable", request=request)

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: async_client(
            transport=httpx.MockTransport(handler), **kwargs
        ),
    )

    with pytest.raises(GitHubMergeUncertainError):
        await merge_pr(17)


def test_pull_request_readiness_requires_mergeability_and_passing_checks():
    ready = {
        "state": "open",
        "draft": False,
        "mergeable": True,
        "mergeable_state": "clean",
    }
    passing = {
        "check_runs": [
            {"status": "completed", "conclusion": "success"},
            {"status": "completed", "conclusion": "skipped"},
        ],
        "statuses": [],
    }
    assert pull_request_readiness_error(ready, passing) is None

    assert pull_request_readiness_error(
        {**ready, "mergeable": False, "mergeable_state": "dirty"},
        passing,
    ) == "PULL_REQUEST_NOT_MERGEABLE"
    assert pull_request_readiness_error(
        {**ready, "mergeable_state": "behind"},
        passing,
    ) == "PULL_REQUEST_OUT_OF_DATE"
    assert pull_request_readiness_error(
        ready,
        {"check_runs": [], "statuses": []},
    ) == "PULL_REQUEST_CHECKS_MISSING"
    assert pull_request_readiness_error(
        ready,
        {
            "check_runs": [{"status": "completed", "conclusion": "failure"}],
            "statuses": [],
        },
    ) == "PULL_REQUEST_CHECKS_FAILED"
