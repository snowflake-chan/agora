import httpx

from app.config import settings


class GitHubPullRequestError(RuntimeError):
    """Raised when a pull request cannot be read from GitHub."""


async def get_pull_request(pr_number: int) -> dict:
    """Return current pull-request metadata from the configured repository."""
    repo = settings.GITHUB_REPO
    if not repo:
        raise GitHubPullRequestError("GITHUB_REPO not configured")

    headers = {"Accept": "application/vnd.github+json"}
    if settings.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"

    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers=headers)

    if resp.status_code == 404:
        raise GitHubPullRequestError("PULL_REQUEST_NOT_FOUND")
    if resp.status_code != 200:
        raise GitHubPullRequestError(
            f"GitHub PR lookup failed ({resp.status_code})"
        )
    return resp.json()


async def merge_pr(pr_number: int) -> bool:
    """Merge a GitHub PR using the bot token. Returns True on success."""
    token = settings.GITHUB_TOKEN
    repo = settings.GITHUB_REPO
    if not token:
        raise RuntimeError("GITHUB_TOKEN not configured")
    if not repo:
        raise RuntimeError("GITHUB_REPO not configured")

    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/merge"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.put(url, headers=headers, json={})

    if resp.status_code in (200, 201):
        return True

    raise RuntimeError(f"GitHub merge failed ({resp.status_code}): {resp.text}")
