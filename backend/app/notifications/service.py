from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db import async_session
from app.db.models.notification import Notification
from app.db.models.follow import Follow
from app.notifications.redis import publish_notification


async def create_notification(
    *,
    recipient_id: UUID,
    type: str,
    title: str,
    message: str,
    link: str,
    dedupe_key: str | None = None,
    required: bool = False,
) -> Notification | None:
    """Persist a notification once, then best-effort its real-time event.

    ``required`` makes database failures visible to durable callers. Redis is
    deliberately not part of that contract: reconnecting clients read the
    authoritative notification row from PostgreSQL.
    """
    try:
        async with async_session() as session:
            inserted = True
            if dedupe_key is not None:
                notif = await session.scalar(
                    insert(Notification)
                    .values(
                        recipient_id=recipient_id,
                        type=type,
                        title=title,
                        message=message,
                        link=link,
                        dedupe_key=dedupe_key,
                    )
                    .on_conflict_do_nothing(
                        index_elements=[Notification.dedupe_key]
                    )
                    .returning(Notification)
                )
                inserted = notif is not None
            else:
                notif = Notification(
                    recipient_id=recipient_id,
                    type=type,
                    title=title,
                    message=message,
                    link=link,
                )
                session.add(notif)
            await session.commit()

            if not inserted:
                return await session.scalar(
                    select(Notification).where(
                        Notification.dedupe_key == dedupe_key
                    )
                )

            if notif is None:
                raise RuntimeError("notification insert returned no row")
            if dedupe_key is None:
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
        if required:
            raise
        print(f"[notif] create error: {e}")
        return None


async def notify_followers(
    *,
    author_id: UUID,
    type: str,
    title: str,
    message: str,
    link: str,
    dedupe_prefix: str | None = None,
    required: bool = False,
) -> None:
    """Create low-priority activity notifications for an author's followers."""
    try:
        async with async_session() as session:
            follower_ids = (
                await session.execute(
                    select(Follow.follower_id).where(
                        Follow.following_id == author_id
                    )
                )
            ).scalars().all()
        for follower_id in follower_ids:
            await create_notification(
                recipient_id=follower_id,
                type=type,
                title=title,
                message=message,
                link=link,
                dedupe_key=(
                    f"{dedupe_prefix}:{follower_id}"
                    if dedupe_prefix is not None
                    else None
                ),
                required=required,
            )
    except Exception as e:
        if required:
            raise
        print(f"[notif] followers error: {e}")
