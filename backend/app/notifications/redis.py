import json

import redis.asyncio as aioredis

from app.config import settings

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Lazy-init Redis connection (singleton)."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=10,
        )
    return _redis


async def publish_notification(
    recipient_id: str,
    payload: dict,
) -> None:
    """Publish notification to the user's Redis channel and bump unread count."""
    try:
        redis = await get_redis()
        channel = f"notif:{recipient_id}"
        await redis.publish(channel, json.dumps(payload))
        await redis.incr(f"notif_unread:{recipient_id}")
    except Exception as e:
        print(f"[notif] Redis publish error: {e}")


async def get_unread_count(user_id: str) -> int:
    """Get unread count from Redis (fast path)."""
    try:
        redis = await get_redis()
        val = await redis.get(f"notif_unread:{user_id}")
        return int(val) if val else 0
    except Exception:
        return 0


async def reset_unread_count(user_id: str) -> None:
    """Reset unread counter to zero (mark-all-read)."""
    try:
        redis = await get_redis()
        await redis.delete(f"notif_unread:{user_id}")
    except Exception:
        pass


async def decrement_unread_count(user_id: str) -> None:
    """Decrement unread counter by 1 (mark-one-read)."""
    try:
        redis = await get_redis()
        val = await redis.decr(f"notif_unread:{user_id}")
        if val < 0:
            await redis.set(f"notif_unread:{user_id}", 0)
    except Exception:
        pass
