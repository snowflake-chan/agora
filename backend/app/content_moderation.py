from dataclasses import dataclass

from sqlalchemy import and_, exists, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.ai.classifier import classify_with_trusted_local_service
from app.ai.errors import AIServiceError
from app.ai.politics import contains_political_signals
from app.config import settings
from app.db.models.content import Content, ContentRevision
from app.db.models.patch import Patch
from app.db.models.user import User


PUBLIC_MODERATION_STATUSES = ("published", "approved")
REVIEWABLE_MODERATION_STATUSES = (
    "pending_review",
    "approved",
    "rejected",
)


@dataclass(frozen=True, slots=True)
class ModerationAssessment:
    status: str
    reason: str | None = None


def content_visibility_clause(
    user: User | None,
    *,
    allow_staff: bool = False,
    model=Content,
):
    """Build a query predicate matching the per-viewer moderation boundary."""
    if allow_staff and user and user.role in ("moderator", "super_admin"):
        return true()
    public = model.moderation_status.in_(PUBLIC_MODERATION_STATUSES)
    if user is not None:
        return or_(public, model.author_id == user.id)
    return public


def content_tree_visibility_clause(
    user: User | None,
    *,
    allow_staff: bool = False,
):
    """Hide comments whenever either the comment or its parent is private."""
    parent = aliased(Content)
    return and_(
        content_visibility_clause(user, allow_staff=allow_staff),
        or_(
            Content.parent_id.is_(None),
            exists(
                select(1).where(
                    parent.id == Content.parent_id,
                    content_visibility_clause(
                        user,
                        allow_staff=allow_staff,
                        model=parent,
                    ),
                )
            ),
        ),
    )


def content_is_visible(
    content: Content,
    user: User | None,
    *,
    allow_staff: bool = False,
) -> bool:
    if content.moderation_status in PUBLIC_MODERATION_STATUSES:
        return True
    if user is not None and content.author_id == user.id:
        return True
    return bool(
        allow_staff
        and user
        and user.role in ("moderator", "super_admin")
    )


def content_is_public(content: Content) -> bool:
    if content.moderation_status not in PUBLIC_MODERATION_STATUSES:
        return False
    return bool(
        content.parent is None
        or content.parent.moderation_status in PUBLIC_MODERATION_STATUSES
    )


def moderation_metadata_for(
    content: Content,
    user: User | None,
    *,
    allow_staff: bool = False,
) -> dict[str, str | None]:
    """Expose review metadata only to the author or an active staff reviewer."""
    privileged = bool(
        user
        and (
            content.author_id == user.id
            or (
                allow_staff
                and user.role in ("moderator", "super_admin")
            )
        )
    )
    if not privileged:
        return {
            "moderation_status": "published",
            "moderation_reason": None,
            "moderation_review_note": None,
        }
    return {
        "moderation_status": content.moderation_status,
        "moderation_reason": content.moderation_reason,
        "moderation_review_note": content.moderation_review_note,
    }


async def assess_content_moderation(*texts: str) -> ModerationAssessment:
    """Conservatively hold political, uncertain, or unclassified content locally."""
    values = [value.strip() for value in texts if value and value.strip()]
    if any(contains_political_signals(value) for value in values):
        return ModerationAssessment(
            status="pending_review",
            reason="political_or_uncertain",
        )

    if settings.AI_POLITICAL_CLASSIFIER_URL.strip():
        try:
            statuses = await classify_with_trusted_local_service(values)
        except AIServiceError:
            # A configured safety dependency failing must not make content public.
            return ModerationAssessment(
                status="pending_review",
                reason="classifier_unavailable",
            )
        if any(status != "non_political" for status in statuses):
            return ModerationAssessment(
                status="pending_review",
                reason="political_or_uncertain",
            )

    return ModerationAssessment(status="published")


def content_href(content: Content) -> str:
    if content.type == "post":
        return f"/posts/{content.id}"
    if content.parent_id is not None:
        return f"/posts/{content.parent_id}#{content.id}"
    if content.patch_id is not None:
        return f"/patches/{content.patch_id}#{content.id}"
    if content.guild_id is not None:
        return f"/guilds/{content.guild_id}#{content.id}"
    return "/"


async def notify_content_pending(content: Content) -> None:
    from app.notifications.service import create_notification

    await create_notification(
        recipient_id=content.author_id,
        type="moderation_pending",
        title="Content awaiting review",
        # Store a stable reason code; clients provide localized explanatory copy.
        message=content.moderation_reason or "",
        link=content_href(content),
        dedupe_key=(
            f"content-moderation-pending:{content.id}:"
            f"v{content.revision_number}"
        ),
    )


async def notify_content_reviewed(
    content: Content,
    *,
    required: bool = False,
) -> None:
    from app.notifications.service import create_notification

    approved = content.moderation_status == "approved"
    await create_notification(
        recipient_id=content.author_id,
        type="moderation_approved" if approved else "moderation_rejected",
        title="Content approved" if approved else "Content not approved",
        message=content.moderation_review_note or "",
        link=content_href(content),
        dedupe_key=(
            f"content-moderation-reviewed:{content.id}:"
            f"v{content.revision_number}"
        ),
        required=required,
    )


async def announce_content_published(
    content: Content,
    *,
    session: AsyncSession | None = None,
    required: bool = False,
) -> None:
    """Emit public side effects only after content becomes visible."""
    from app.notifications.service import create_notification, notify_followers
    from app.posts.realtime import publish_feed_event

    previously_public = False
    if session is not None and content.revision_number > 1:
        previously_public = bool(
            await session.scalar(
                select(ContentRevision.id).where(
                    ContentRevision.content_id == content.id,
                    ContentRevision.was_public.is_(True),
                ).limit(1)
            )
        )

    # Re-approval of an edited public item is an update, not a second
    # publication. It must not notify followers or reply recipients again.
    if previously_public:
        if content.type == "post":
            await publish_feed_event(
                "updated",
                item_type="post",
                item_id=str(content.id),
                event_id=(
                    f"content-published:{content.id}:"
                    f"v{content.revision_number}"
                ),
                required=required,
            )
        elif content.patch_id is not None:
            await publish_feed_event(
                "updated",
                item_type="patch",
                item_id=str(content.patch_id),
                event_id=(
                    f"content-published:{content.id}:"
                    f"v{content.revision_number}"
                ),
                required=required,
            )
        elif content.parent_id is not None:
            await publish_feed_event(
                "updated",
                item_type="post",
                item_id=str(content.parent_id),
                event_id=(
                    f"content-published:{content.id}:"
                    f"v{content.revision_number}"
                ),
                required=required,
            )
        return

    if content.type == "post":
        await publish_feed_event(
            "created",
            item_type="post",
            item_id=str(content.id),
            event_id=(
                f"content-published:{content.id}:v{content.revision_number}"
            ),
            required=required,
        )
        await notify_followers(
            author_id=content.author_id,
            type="following_post",
            title=(
                f"{content.author.nickname or content.author.username} "
                "published a new post"
            ),
            message=content.title or "",
            link=f"/posts/{content.id}",
            dedupe_prefix=(
                f"content-published:{content.id}:"
                f"v{content.revision_number}:following"
            ),
            required=required,
        )
        return

    if content.type == "guild_post":
        return

    if content.type != "comment":
        return

    if content.parent_id is None and content.guild_id is not None:
        return

    if content.parent_id is None and content.patch_id is not None:
        if session is None:
            return
        patch = await session.scalar(select(Patch).where(Patch.id == content.patch_id))
        if patch is None or patch.status == "draft":
            return

        author_name = content.author.nickname or content.author.username
        notified: set = set()
        if patch.author_id != content.author_id:
            await create_notification(
                recipient_id=patch.author_id,
                type="reply",
                title="New change discussion",
                message=f'{author_name} commented on "{patch.title}"',
                link=f"/patches/{patch.id}#{content.id}",
                dedupe_key=(
                    f"content-published:{content.id}:"
                    f"v{content.revision_number}:reply:{patch.author_id}"
                ),
                required=required,
            )
            notified.add(patch.author_id)
        if (
            content.replying_to
            and content.replying_to.author_id != content.author_id
            and content.replying_to.author_id not in notified
        ):
            await create_notification(
                recipient_id=content.replying_to.author_id,
                type="reply",
                title="New discussion reply",
                message=f"{author_name} replied to your comment",
                link=f"/patches/{patch.id}#{content.id}",
                dedupe_key=(
                    "content-published:"
                    f"{content.id}:v{content.revision_number}:"
                    f"reply:{content.replying_to.author_id}"
                ),
                required=required,
            )
        await publish_feed_event(
            "updated",
            item_type="patch",
            item_id=str(patch.id),
            event_id=(
                f"content-published:{content.id}:v{content.revision_number}"
            ),
            required=required,
        )
        return

    if content.parent_id is None:
        return

    author_name = content.author.nickname or content.author.username
    notified: set = set()
    if content.parent and content.parent.author_id != content.author_id:
        await create_notification(
            recipient_id=content.parent.author_id,
            type="reply",
            title="New reply",
            message=(
                f'{author_name} replied to your post '
                f'"{content.parent.title or ""}"'
            ),
            link=f"/posts/{content.parent_id}#{content.id}",
            dedupe_key=(
                f"content-published:{content.id}:"
                f"v{content.revision_number}:reply:{content.parent.author_id}"
            ),
            required=required,
        )
        notified.add(content.parent.author_id)

    if (
        content.replying_to
        and content.replying_to.author_id != content.author_id
        and content.replying_to.author_id not in notified
    ):
        await create_notification(
            recipient_id=content.replying_to.author_id,
            type="reply",
            title="New reply",
            message=f"{author_name} replied to your comment",
            link=f"/posts/{content.parent_id}#{content.id}",
            dedupe_key=(
                "content-published:"
                f"{content.id}:v{content.revision_number}:"
                f"reply:{content.replying_to.author_id}"
            ),
            required=required,
        )

    await publish_feed_event(
        "updated",
        item_type="post",
        item_id=str(content.parent_id),
        event_id=f"content-published:{content.id}:v{content.revision_number}",
        required=required,
    )
