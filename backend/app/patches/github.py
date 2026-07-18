import httpx

from app.config import settings


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
