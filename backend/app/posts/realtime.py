import json

from app.notifications.redis import get_redis

FEED_CHANNEL = "feed:events"


async def publish_feed_event(
    event_type: str,
    *,
    item_type: str | None = None,
    item_id: str | None = None,
    event_id: str | None = None,
    required: bool = False,
) -> None:
    """Notify connected home feeds that their first page may have changed."""
    try:
        redis = await get_redis()
        await redis.publish(
            FEED_CHANNEL,
            json.dumps(
                {
                    "type": event_type,
                    "item_type": item_type,
                    "item_id": item_id,
                    "event_id": event_id,
                }
            ),
        )
    except Exception as exc:
        if required:
            raise
        print(f"[feed] Redis publish error: {exc}")
