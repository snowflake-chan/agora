import hashlib

from fastapi import HTTPException, Request

from app.notifications.redis import get_redis


_INCREMENT_SCRIPT = """
local current = redis.call("INCR", KEYS[1])
if current == 1 then
    redis.call("EXPIRE", KEYS[1], ARGV[1])
end
return {current, redis.call("TTL", KEYS[1])}
"""


def client_ip(request: Request) -> str:
    """Return the client IP set by the trusted internal nginx proxy."""
    forwarded = request.headers.get("x-real-ip")
    if forwarded:
        return forwarded.strip()
    if request.client:
        return request.client.host
    return "unknown"


def _key(scope: str, identifier: str) -> str:
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
    return f"rate_limit:{scope}:{digest}"


async def enforce_rate_limit(
    *,
    scope: str,
    identifier: str,
    limit: int,
    window_seconds: int,
) -> None:
    """Increment an atomic fixed-window counter and reject excess requests."""
    if limit < 1 or window_seconds < 1:
        return

    try:
        redis = await get_redis()
        count, ttl = await redis.eval(
            _INCREMENT_SCRIPT,
            1,
            _key(scope, identifier),
            window_seconds,
        )
    except Exception as exc:
        # Authentication should remain available during a Redis outage.
        print(f"[rate-limit] Redis unavailable: {exc}")
        return

    if int(count) > limit:
        retry_after = max(int(ttl), 1)
        raise HTTPException(
            status_code=429,
            detail="RATE_LIMIT_EXCEEDED",
            headers={"Retry-After": str(retry_after)},
        )
