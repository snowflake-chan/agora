from uuid import UUID

from app.db import async_session
from app.db.models.notification import Notification
from app.notifications.redis import publish_notification


async def create_notification(
    *,
    recipient_id: UUID,
    type: str,
    title: str,
    message: str,
    link: str,
) -> Notification | None:
    """Create a notification record and publish real-time event via Redis."""
    try:
        async with async_session() as session:
            notif = Notification(
                recipient_id=recipient_id,
                type=type,
                title=title,
                message=message,
                link=link,
            )
            session.add(notif)
            await session.commit()
            await session.refresh(notif)

            # Fire-and-forget Redis publish
            await publish_notification(
                str(recipient_id),
                {
                    "id": str(notif.id),
                    "type": notif.type,
                    "title": notif.title,
                    "message": notif.message,
                    "link": notif.link,
                    "created_at": notif.created_at.isoformat(),
                },
            )

            return notif
    except Exception as e:
        print(f"[notif] create error: {e}")
        return None
