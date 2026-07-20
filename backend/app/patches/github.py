import httpx

from app.config import settings


class GitHubPullRequestError(RuntimeError):
    """Raised when a pull request cannot be read from GitHub."""


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    if settings.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"
    return headers


async def get_pull_request(pr_number: int) -> dict:
    """Return current pull-request metadata from the configured repository."""
    repo = settings.GITHUB_REPO
    if not repo:
        raise GitHubPullRequestError("GITHUB_REPO not configured")

    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers=_headers())

    if resp.status_code == 404:
        raise GitHubPullRequestError("PULL_REQUEST_NOT_FOUND")
    if resp.status_code != 200:
        raise GitHubPullRequestError(
            f"GitHub PR lookup failed ({resp.status_code})"
        )
    return resp.json()


async def get_commit_checks(commit_sha: str) -> dict:
    """Return check runs and legacy commit statuses for a PR head commit."""
    repo = settings.GITHUB_REPO
    if not repo:
        raise GitHubPullRequestError("GITHUB_REPO not configured")

    base = f"https://api.github.com/repos/{repo}/commits/{commit_sha}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        checks_response = await client.get(
            f"{base}/check-runs",
            headers=_headers(),
            params={"per_page": 100},
        )
        status_response = await client.get(
            f"{base}/status",
            headers=_headers(),
        )

    if checks_response.status_code != 200 or status_response.status_code != 200:
        raise GitHubPullRequestError("GITHUB_CHECK_LOOKUP_FAILED")
    return {
        "check_runs": checks_response.json().get("check_runs", []),
        "statuses": status_response.json().get("statuses", []),
    }


def pull_request_readiness_error(
    pull_request: dict,
    commit_checks: dict,
) -> str | None:
    """Return a stable error code when a PR is not ready for governance."""
    if pull_request.get("state") != "open":
        return "PULL_REQUEST_NOT_OPEN"
    if pull_request.get("draft"):
        return "PULL_REQUEST_IS_DRAFT"

    mergeable = pull_request.get("mergeable")
    mergeable_state = pull_request.get("mergeable_state")
    if mergeable is False or mergeable_state == "dirty":
        return "PULL_REQUEST_NOT_MERGEABLE"
    if mergeable_state == "behind":
        return "PULL_REQUEST_OUT_OF_DATE"
    if mergeable is None or mergeable_state in (None, "unknown"):
        return "PULL_REQUEST_READINESS_PENDING"
    if mergeable_state == "blocked":
        return "PULL_REQUEST_BLOCKED"

    check_runs = commit_checks.get("check_runs", [])
    statuses = commit_checks.get("statuses", [])
    if not check_runs and not statuses:
        return "PULL_REQUEST_CHECKS_MISSING"

    if any(run.get("status") != "completed" for run in check_runs):
        return "PULL_REQUEST_CHECKS_PENDING"
    passing_conclusions = {"success", "neutral", "skipped"}
    if any(run.get("conclusion") not in passing_conclusions for run in check_runs):
        return "PULL_REQUEST_CHECKS_FAILED"

    if any(status.get("state") == "pending" for status in statuses):
        return "PULL_REQUEST_CHECKS_PENDING"
    if any(status.get("state") not in ("success",) for status in statuses):
        return "PULL_REQUEST_CHECKS_FAILED"
    return None


async def merge_pr(pr_number: int) -> bool:
    """Merge a GitHub PR using the bot token. Returns True on success."""
    token = settings.GITHUB_TOKEN
    repo = settings.GITHUB_REPO
    if not token:
        raise RuntimeError("GITHUB_TOKEN not configured")
    if not repo:
        raise RuntimeError("GITHUB_REPO not configured")

    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/merge"
    headers = _headers()

    async with httpx.AsyncClient() as client:
        resp = await client.put(url, headers=headers, json={})

    if resp.status_code in (200, 201):
        return True

    raise RuntimeError(f"GitHub merge failed ({resp.status_code}): {resp.text}")
