import re

import httpx

from app.config import settings


def _parse_pr_url(url: str) -> tuple[str, str, int] | None:
    """Parse a GitHub PR URL into owner, repo, and PR number.

    Supports formats:
    - https://github.com/owner/repo/pull/123
    - https://github.com/owner/repo/pull/123/
    """
    m = re.match(r"https?://github\.com/([\w.-]+)/([\w.-]+)/pull/(\d+)/?$", url)
    if not m:
        return None
    return m.group(1), m.group(2), int(m.group(3))


async def merge_pr(pr_url: str) -> bool:
    """Merge a GitHub PR using the bot token. Returns True on success."""
    parsed = _parse_pr_url(pr_url)
    if not parsed:
        raise ValueError(f"Invalid PR URL: {pr_url}")

    owner, repo, number = parsed
    token = settings.GITHUB_TOKEN
    if not token:
        raise RuntimeError("GITHUB_TOKEN not configured")

    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}/merge"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.put(url, headers=headers, json={})

    if resp.status_code in (200, 201):
        return True

    raise RuntimeError(f"GitHub merge failed ({resp.status_code}): {resp.text}")
