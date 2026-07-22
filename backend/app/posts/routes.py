import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, literal, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.db import get_session
from app.db.models.content import Content as ContentModel, ContentRevision
from app.db.models.content_boost import ContentBoost
from app.db.models.follow import Follow
from app.db.models.patch import Patch as PatchModel
from app.db.models.post_like import PostLike
from app.db.models.post_poll import PostPoll, PostPollOption, PostPollVote
from app.db.models.user import User
from app.db.models.vote import Vote as VoteModel
from app.deps import (
    check_not_banned,
    require_content_interactable,
    require_content_visible,
)
from app.content_moderation import (
    PUBLIC_MODERATION_STATUSES,
    announce_content_published,
    assess_content_moderation_after_read,
    content_is_public,
    content_tree_visibility_clause,
    content_visibility_clause,
    moderation_metadata_for,
    notify_content_pending,
)
from app.schemas.content_input import validate_moderation_input_size
from app.notifications.redis import get_redis
from app.post_polls import create_post_poll, load_post_polls
from app.posts.feed import FeedMode, rank_feed_items
from app.posts.realtime import FEED_CHANNEL, publish_feed_event
from app.schemas.post import (
    CommentCreate,
    CommentRead,
    ContentBoostCreate,
    ContentEditRead,
    ContentRevisionRead,
    FeedItem,
    PollRead,
    PollVoteCreate,
    PostCreate,
    PostLikeRead,
    PostRead,
    PostUpdate,
)
from app.tokens import service as token_service
from app.users.deps import current_user, optional_current_user

router = APIRouter()


def _content_edit_read(content: ContentModel, user: User) -> ContentEditRead:
    return ContentEditRead(
        id=content.id,
        type=content.type,
        title=content.title,
        content=content.content,
        tags=content.tags,
        author_id=content.author_id,
        parent_id=content.parent_id,
        patch_id=content.patch_id,
        guild_id=content.guild_id,
        **moderation_metadata_for(content, user),
        revision_number=content.revision_number,
        created_at=content.created_at,
        updated_at=content.updated_at,
    )


async def _publish_content_edit(
    content: ContentModel,
    *,
    hidden: bool = False,
) -> None:
    """Refresh only the public root affected by an edit."""
    if content.type == "post":
        await publish_feed_event(
            "removed" if hidden else "updated",
            item_type="post",
            item_id=str(content.id),
        )
    elif content.patch_id is not None:
        await publish_feed_event(
            "updated",
            item_type="patch",
            item_id=str(content.patch_id),
        )
    elif content.parent_id is not None:
        await publish_feed_event(
            "updated",
            item_type="post",
            item_id=str(content.parent_id),
        )


async def _content_is_public_for_edit(
    session: AsyncSession,
    content: ContentModel,
) -> bool:
    """Check inherited visibility without triggering an async lazy load."""
    if content.moderation_status not in PUBLIC_MODERATION_STATUSES:
        return False
    if content.parent_id is None:
        return True
    parent_status = await session.scalar(
        select(ContentModel.moderation_status).where(
            ContentModel.id == content.parent_id
        )
    )
    return parent_status in PUBLIC_MODERATION_STATUSES


# ── Posts ──


@router.get("", response_model=list[PostRead])
async def list_posts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(optional_current_user),
):
    """List posts (type=post), newest first."""
    offset = (page - 1) * page_size

    # Count total
    total = await session.scalar(
        select(func.count(ContentModel.id)).where(
            ContentModel.type == "post",
            content_visibility_clause(user),
        )
    )

    # Fetch posts with author
    stmt = (
        select(ContentModel)
        .where(
            ContentModel.type == "post",
            content_visibility_clause(user),
        )
        .order_by(ContentModel.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    posts = result.scalars().all()

    # Attach reply counts
    post_ids = [p.id for p in posts]
    counts = {}
    like_counts = {}
    if post_ids:
        count_stmt = (
            select(ContentModel.parent_id, func.count(ContentModel.id))
            .where(
                ContentModel.parent_id.in_(post_ids),
                ContentModel.type == "comment",
                content_visibility_clause(user),
            )
            .group_by(ContentModel.parent_id)
        )
        count_result = await session.execute(count_stmt)
        counts = dict(count_result.all())
        like_result = await session.execute(
            select(PostLike.post_id, func.count(PostLike.id))
            .where(PostLike.post_id.in_(post_ids))
            .group_by(PostLike.post_id)
        )
        like_counts = dict(like_result.all())
    polls_by_post = await load_post_polls(
        session,
        post_ids,
        viewer_id=user.id if user else None,
    )

    return [
        PostRead(
            id=p.id,
            title=p.title or "",
            content=p.content,
            author_id=p.author_id,
            tags=p.tags,
            author_username=p.author.username,
            reply_count=counts.get(p.id, 0),
            like_count=like_counts.get(p.id, 0),
            poll=polls_by_post.get(p.id),
            **moderation_metadata_for(p, user),
            revision_number=p.revision_number,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in posts
    ]


@router.post("", response_model=PostRead, status_code=201)
async def create_post(
    data: PostCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Create a new post."""
    await check_not_banned(user.id, session, "mute_post")
    if not data.title.strip():
        raise HTTPException(status_code=422, detail="Title is required")
    if not data.content.strip():
        raise HTTPException(status_code=422, detail="Content is required")

    moderation_texts = [data.title, data.content, *(data.tags or [])]
    if data.poll is not None:
        moderation_texts.extend(
            [data.poll.question, *data.poll.options]
        )
    moderation = await assess_content_moderation_after_read(
        session,
        *moderation_texts,
    )

    # The read transaction was released during semantic review. Recheck the
    # mutable restriction in the short write transaction.
    await check_not_banned(user.id, session, "mute_post")

    post = ContentModel(
        type="post",
        title=data.title.strip(),
        content=data.content.strip(),
        tags=data.tags,
        author_id=user.id,
        moderation_status=moderation.status,
        moderation_reason=moderation.reason,
        published_at=(
            datetime.now(timezone.utc)
            if moderation.status == "published"
            else None
        ),
    )
    session.add(post)
    await session.flush()
    if data.poll is not None:
        await create_post_poll(session, post_id=post.id, data=data.poll)
    await session.commit()

    # Eagerly load author
    stmt = select(ContentModel).where(ContentModel.id == post.id)
    result = await session.execute(stmt)
    post = result.scalar_one()
    polls_by_post = await load_post_polls(session, [post.id], viewer_id=user.id)

    if post.moderation_status == "pending_review":
        await notify_content_pending(post)
    else:
        await announce_content_published(post, session=session)

    return PostRead(
        id=post.id,
        title=post.title or "",
        content=post.content,
        author_id=post.author_id,
        tags=post.tags,
        author_username=post.author.username,
        reply_count=0,
        poll=polls_by_post.get(post.id),
        **moderation_metadata_for(post, user),
        revision_number=post.revision_number,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


# ── Feed (unified timeline) ──


@router.patch("/{content_id}", response_model=ContentEditRead)
async def update_content(
    content_id: UUID,
    data: PostUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Edit owned content while preserving the superseded version forever."""
    candidate = await session.scalar(
        select(ContentModel).where(ContentModel.id == content_id)
    )
    candidate = await require_content_visible(candidate, user, session)
    if candidate.author_id != user.id:
        raise HTTPException(status_code=403, detail="FORBIDDEN")
    if candidate.type not in ("post", "comment", "guild_post"):
        raise HTTPException(status_code=422, detail="CONTENT_NOT_EDITABLE")
    if candidate.revision_number != data.revision_number:
        raise HTTPException(status_code=409, detail="CONTENT_EDIT_CONFLICT")

    if candidate.type == "post" and await session.scalar(
        select(PostPoll.id).where(PostPoll.post_id == candidate.id)
    ):
        raise HTTPException(status_code=409, detail="POLL_CONTENT_EDIT_LOCKED")

    fields = data.model_fields_set - {"revision_number"}
    allowed_fields = {
        "post": {"title", "content", "tags"},
        "comment": {"content"},
        "guild_post": {"title", "content"},
    }[candidate.type]
    if not fields:
        raise HTTPException(status_code=422, detail="CONTENT_UPDATE_REQUIRED")
    if fields - allowed_fields:
        raise HTTPException(status_code=422, detail="CONTENT_FIELD_NOT_EDITABLE")

    new_title = candidate.title
    new_content = candidate.content
    new_tags = candidate.tags
    if "title" in fields:
        new_title = data.title.strip() if data.title is not None else None
        if candidate.type == "post" and not new_title:
            raise HTTPException(status_code=422, detail="TITLE_REQUIRED")
        if new_title is not None and len(new_title) > 200:
            raise HTTPException(status_code=422, detail="TITLE_TOO_LONG")
    if "content" in fields:
        new_content = data.content.strip() if data.content is not None else ""
        if not new_content:
            raise HTTPException(status_code=422, detail="CONTENT_REQUIRED")
    if "tags" in fields:
        new_tags = (
            None if data.tags is None else [tag.strip() for tag in data.tags]
        )
        if new_tags and any(len(tag) > 50 for tag in new_tags):
            raise HTTPException(status_code=422, detail="TAG_TOO_LONG")

    if (
        new_title == candidate.title
        and new_content == candidate.content
        and new_tags == candidate.tags
    ):
        raise HTTPException(status_code=422, detail="CONTENT_NO_CHANGES")

    base_revision = data.revision_number
    try:
        validate_moderation_input_size(
            [new_title or "", new_content, *(new_tags or [])]
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail="AI_INPUT_TOO_LONG") from error

    moderation = await assess_content_moderation_after_read(
        session,
        new_title or "",
        new_content,
        *(new_tags or []),
    )

    # Only lock the scalar ID. Content's eager author/parent joins include
    # nullable relationships that PostgreSQL cannot lock with FOR UPDATE.
    locked_id = await session.scalar(
        select(ContentModel.id)
        .where(ContentModel.id == content_id)
        .with_for_update()
    )
    if locked_id is None:
        raise HTTPException(status_code=404, detail="CONTENT_NOT_FOUND")
    content = await session.scalar(
        select(ContentModel)
        .where(ContentModel.id == locked_id)
        .execution_options(populate_existing=True)
    )
    content = await require_content_visible(content, user, session)
    if content.author_id != user.id:
        raise HTTPException(status_code=403, detail="FORBIDDEN")
    if content.revision_number != base_revision:
        raise HTTPException(status_code=409, detail="CONTENT_EDIT_CONFLICT")
    if content.type == "post" and await session.scalar(
        select(PostPoll.id).where(PostPoll.post_id == content.id)
    ):
        raise HTTPException(status_code=409, detail="POLL_CONTENT_EDIT_LOCKED")

    await check_not_banned(
        user.id,
        session,
        "mute_patch" if content.patch_id is not None else "mute_post",
    )
    was_public = await _content_is_public_for_edit(session, content)
    edited_at = await session.scalar(select(func.clock_timestamp()))
    session.add(
        ContentRevision(
            content_id=content.id,
            version=content.revision_number,
            title=content.title,
            content=content.content,
            tags=content.tags,
            editor_id=user.id,
            was_public=was_public,
            edited_at=edited_at,
        )
    )
    content.title = new_title
    content.content = new_content
    content.tags = new_tags
    content.revision_number += 1
    content.updated_at = edited_at
    content.moderation_status = moderation.status
    content.moderation_reason = moderation.reason
    content.moderation_review_note = None
    content.moderation_reviewed_by = None
    content.moderation_reviewed_at = None
    content.moderation_effects_completed_at = None
    if (
        moderation.status != "pending_review"
        and not was_public
        and content.published_at is None
    ):
        content.published_at = edited_at

    await session.commit()
    content = await session.scalar(
        select(ContentModel).where(ContentModel.id == content_id)
    )
    if content is None:
        raise HTTPException(status_code=404, detail="CONTENT_NOT_FOUND")

    if content.moderation_status == "pending_review":
        await notify_content_pending(content)
        if was_public:
            await _publish_content_edit(content, hidden=True)
    elif was_public:
        await _publish_content_edit(content)
    elif await _content_is_public_for_edit(session, content):
        await announce_content_published(content, session=session)

    return _content_edit_read(content, user)


@router.get(
    "/{content_id}/history",
    response_model=list[ContentRevisionRead],
)
async def get_content_history(
    content_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(optional_current_user),
):
    """Return immutable snapshots visible under the current privacy boundary."""
    allow_staff = bool(user and user.role in ("moderator", "super_admin"))
    content = await session.scalar(
        select(ContentModel).where(ContentModel.id == content_id)
    )
    content = await require_content_visible(
        content,
        user,
        session,
        allow_staff=allow_staff,
    )
    privileged = bool(
        user
        and (
            content.author_id == user.id
            or user.role in ("moderator", "super_admin")
        )
    )
    stmt = select(ContentRevision).where(
        ContentRevision.content_id == content.id
    )
    if not privileged:
        # A never-published held draft cannot become public through history.
        stmt = stmt.where(ContentRevision.was_public.is_(True))
    revisions = (
        await session.execute(stmt.order_by(ContentRevision.version.desc()))
    ).scalars().all()
    return [ContentRevisionRead.model_validate(item) for item in revisions]


@router.get("/-/feed", response_model=list[FeedItem])
async def get_feed(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    mode: FeedMode = Query("recommended"),
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(optional_current_user),
):
    """Unified feed ranked for the requested home view."""
    offset = (page - 1) * page_size
    if mode == "following" and user is None:
        raise HTTPException(status_code=401, detail="LOGIN_REQUIRED")

    following_author_ids: set[UUID] = set()
    interest_tags: set[str] = set()
    if user:
        following_author_ids = set(
            (
                await session.execute(
                    select(Follow.following_id).where(
                        Follow.follower_id == user.id
                    )
                )
            )
            .scalars()
            .all()
        )
        authored_tags = (
            await session.execute(
                select(ContentModel.tags)
                .where(
                    ContentModel.type == "post",
                    ContentModel.author_id == user.id,
                    ContentModel.tags.is_not(None),
                    content_visibility_clause(user),
                )
                .order_by(ContentModel.created_at.desc())
                .limit(50)
            )
        ).scalars().all()
        liked_tags = (
            await session.execute(
                select(ContentModel.tags)
                .join(PostLike, PostLike.post_id == ContentModel.id)
                .where(
                    ContentModel.type == "post",
                    PostLike.user_id == user.id,
                    ContentModel.tags.is_not(None),
                    content_visibility_clause(user),
                )
                .order_by(ContentModel.created_at.desc())
                .limit(50)
            )
        ).scalars().all()
        for tags in [*authored_tags, *liked_tags]:
            interest_tags.update(tag.casefold() for tag in tags or [])

    # Fetch a bounded candidate pool; ranking happens after all signals are attached.
    now = datetime.now(timezone.utc)
    posts = (
        await session.execute(
            select(ContentModel)
            .where(
                ContentModel.type == "post",
                content_visibility_clause(user),
            )
            .order_by(
                func.coalesce(
                    ContentModel.published_at,
                    ContentModel.created_at,
                ).desc()
            )
            .limit(500)
        )
    ).scalars().all()

    patch_visibility = PatchModel.status != "draft"
    if user is not None:
        patch_visibility = or_(
            patch_visibility,
            PatchModel.author_id == user.id,
        )
    patches = (
        await session.execute(
            select(PatchModel)
            .where(patch_visibility)
            .order_by(PatchModel.created_at.desc())
            .limit(500)
        )
    ).scalars().all()

    post_ids = [p.id for p in posts]
    reply_counts: dict = {}
    like_counts: dict = {}
    boost_weights: dict[UUID, float] = {}
    if post_ids:
        count_stmt = (
            select(ContentModel.parent_id, func.count(ContentModel.id))
            .where(
                ContentModel.parent_id.in_(post_ids),
                ContentModel.type == "comment",
                content_visibility_clause(user),
            )
            .group_by(ContentModel.parent_id)
        )
        count_result = await session.execute(count_stmt)
        reply_counts = dict(count_result.all())
        like_result = await session.execute(
            select(PostLike.post_id, func.count(PostLike.id))
            .where(PostLike.post_id.in_(post_ids))
            .group_by(PostLike.post_id)
        )
        like_counts = dict(like_result.all())
        
        polls_by_post = await load_post_polls(
            session,
            post_ids,
            viewer_id=user.id if user else None,
        )
        
        boost_result = await session.execute(
            select(ContentBoost.content_id, ContentBoost.weight)
            .where(
                ContentBoost.content_id.in_(post_ids),
                ContentBoost.expires_at > now,
            )
        )
        boost_weights = {row[0]: row[1] for row in boost_result.all()}

    patch_comment_counts: dict = {}
    patch_ids = [p.id for p in patches]
    if patch_ids:
        patch_comment_counts = dict(
            (
                await session.execute(
                    select(ContentModel.patch_id, func.count(ContentModel.id))
                    .where(
                        ContentModel.patch_id.in_(patch_ids),
                        ContentModel.type == "comment",
                        content_visibility_clause(user),
                    )
                    .group_by(ContentModel.patch_id)
                )
            ).all()
        )
    vote_counts: dict[str, dict[str, int]] = {}
    if patch_ids:
        vote_rows = (
            await session.execute(
                select(VoteModel.patch_id, VoteModel.choice, func.count(VoteModel.id))
                .where(VoteModel.patch_id.in_(patch_ids))
                .group_by(VoteModel.patch_id, VoteModel.choice)
            )
        ).all()
        for patch_id, choice, count in vote_rows:
            vote_counts.setdefault(
                str(patch_id),
                {"for": 0, "against": 0, "abstain": 0},
            )[choice] = count

    items: list[FeedItem] = []
    for p in posts:
        feed_published_at = p.published_at or p.created_at
        items.append(FeedItem(
            id=p.id, type="post", title=p.title or "", content=p.content,
            author_id=p.author_id, author_username=p.author.username,
            created_at=feed_published_at, tags=p.tags,
            reply_count=reply_counts.get(p.id, 0),
            like_count=like_counts.get(p.id, 0),
            poll=polls_by_post.get(p.id),
            boost_weight=boost_weights.get(p.id, 1.0),
            **moderation_metadata_for(p, user),
            revision_number=p.revision_number,
        ))

    for p in patches:
        items.append(FeedItem(
            id=p.id, type="patch", title=p.title, content=p.content,
            author_id=p.author_id, author_username=p.author.username,
            created_at=p.created_at,
            pr_number=p.pr_number, status=p.status,
            voting_started_at=p.voting_started_at,
            voting_ends_at=p.voting_ends_at,
            voting_period_hours=p.voting_period_hours,
            voting_window_kind=p.voting_window_kind,
            reply_count=patch_comment_counts.get(p.id, 0),
            for_count=vote_counts.get(str(p.id), {}).get("for", 0),
            against_count=vote_counts.get(str(p.id), {}).get("against", 0),
            abstain_count=vote_counts.get(str(p.id), {}).get("abstain", 0),
            revision_number=p.revision_number,
        ))

    ranked = rank_feed_items(
        items,
        mode=mode,
        following_author_ids=following_author_ids,
        interest_tags=interest_tags,
    )
    return ranked[offset:offset + page_size]


@router.get("/-/feed/stream")
async def feed_stream():
    """SSE stream for home feed changes shared by all connected visitors."""

    async def event_generator():
        redis = await get_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(FEED_CHANNEL)
        try:
            while True:
                message = await pubsub.get_message(timeout=25.0)
                if message and message["type"] == "message":
                    yield {
                        "event": "feed",
                        "data": message["data"],
                    }
                else:
                    yield {"comment": "ping"}
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(FEED_CHANNEL)
            await pubsub.close()

    return EventSourceResponse(event_generator())


@router.get("/{post_id}", response_model=PostRead)
async def get_post(
    post_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(optional_current_user),
):
    """Get a single post by ID."""
    allow_staff = bool(user and user.role in ("moderator", "super_admin"))
    stmt = select(ContentModel).where(
        ContentModel.id == post_id, ContentModel.type == "post"
    )
    result = await session.execute(stmt)
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="POST_NOT_FOUND")
    try:
        post = await require_content_visible(
            post,
            user,
            session,
            allow_staff=allow_staff,
        )
    except HTTPException as error:
        if error.detail == "CONTENT_NOT_FOUND":
            raise HTTPException(status_code=404, detail="POST_NOT_FOUND") from error
        raise

    # Count replies
    reply_count = await session.scalar(
        select(func.count(ContentModel.id)).where(
            ContentModel.parent_id == post.id,
            ContentModel.type == "comment",
            content_visibility_clause(user, allow_staff=allow_staff),
        )
    )
    like_count = await session.scalar(
        select(func.count(PostLike.id)).where(PostLike.post_id == post.id)
    )
    liked_by_me = False
    if user:
        liked_by_me = bool(
            await session.scalar(
                select(PostLike.id).where(
                    PostLike.post_id == post.id, PostLike.user_id == user.id
                )
            )
        )
    polls_by_post = await load_post_polls(
        session,
        [post.id],
        viewer_id=user.id if user else None,
    )

    return PostRead(
        id=post.id,
        title=post.title or "",
        content=post.content,
        author_id=post.author_id,
        tags=post.tags,
        author_username=post.author.username,
        reply_count=reply_count or 0,
        like_count=like_count or 0,
        liked_by_me=liked_by_me,
        poll=polls_by_post.get(post.id),
        **moderation_metadata_for(post, user, allow_staff=allow_staff),
        revision_number=post.revision_number,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


@router.put("/{post_id}/poll/vote", response_model=PollRead)
async def vote_on_post_poll(
    post_id: UUID,
    data: PollVoteCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Cast or replace the caller's selection while the poll remains open."""
    await check_not_banned(user.id, session)
    poll = await session.scalar(
        select(PostPoll).where(PostPoll.post_id == post_id)
    )
    if poll is None:
        raise HTTPException(status_code=404, detail="POLL_NOT_FOUND")
    post = await session.scalar(
        select(ContentModel).where(
            ContentModel.id == post_id,
            ContentModel.type == "post",
        )
    )
    post = await require_content_interactable(post, user, session)

    database_now = await session.scalar(select(func.clock_timestamp()))
    if poll.closes_at <= database_now:
        raise HTTPException(status_code=409, detail="POLL_CLOSED")

    option_exists = await session.scalar(
        select(PostPollOption.id).where(
            PostPollOption.id == data.option_id,
            PostPollOption.poll_id == poll.id,
        )
    )
    if option_exists is None:
        raise HTTPException(status_code=404, detail="POLL_OPTION_NOT_FOUND")

    # The unique key is the concurrency boundary: one voter has one mutable choice.
    vote_source = (
        select(
            literal(uuid4()),
            PostPoll.id,
            PostPollOption.id,
            literal(user.id),
            func.clock_timestamp(),
            func.clock_timestamp(),
        )
        .select_from(PostPoll)
        .join(
            PostPollOption,
            (PostPollOption.poll_id == PostPoll.id)
            & (PostPollOption.id == data.option_id),
        )
        .where(
            PostPoll.id == poll.id,
            PostPoll.closes_at > func.clock_timestamp(),
        )
    )
    vote_result = await session.execute(
        insert(PostPollVote)
        .from_select(
            (
                "id",
                "poll_id",
                "option_id",
                "user_id",
                "created_at",
                "updated_at",
            ),
            vote_source,
        )
        .on_conflict_do_update(
            constraint="uq_post_poll_vote_poll_user",
            set_={
                "option_id": data.option_id,
                "updated_at": func.clock_timestamp(),
            },
        )
        .returning(PostPollVote.option_id)
    )
    if vote_result.scalar_one_or_none() is None:
        await session.rollback()
        raise HTTPException(status_code=409, detail="POLL_CLOSED")
    await session.commit()
    polls_by_post = await load_post_polls(
        session,
        [post_id],
        viewer_id=user.id,
    )
    updated_poll = polls_by_post.get(post_id)
    if updated_poll is None:
        raise HTTPException(status_code=404, detail="POLL_NOT_FOUND")
    if post and content_is_public(post):
        await publish_feed_event("updated", item_type="post", item_id=str(post_id))
    return updated_poll


async def _post_like_state(
    session: AsyncSession, post_id: UUID, user_id
) -> PostLikeRead:
    like_count = await session.scalar(
        select(func.count(PostLike.id)).where(PostLike.post_id == post_id)
    )
    liked_by_me = bool(
        await session.scalar(
            select(PostLike.id).where(
                PostLike.post_id == post_id, PostLike.user_id == user_id
            )
        )
    )
    return PostLikeRead(like_count=like_count or 0, liked_by_me=liked_by_me)


@router.put("/{post_id}/like", response_model=PostLikeRead)
async def like_post(
    post_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Like a post. Repeated requests are idempotent."""
    await check_not_banned(user.id, session)
    content = await session.scalar(
        select(ContentModel).where(
            ContentModel.id == post_id, ContentModel.type.in_(("post", "comment"))
        )
    )
    content = await require_content_interactable(content, user, session)

    # Check if already liked before inserting (to avoid duplicate token rewards)
    already_liked = await session.scalar(
        select(PostLike).where(
            PostLike.post_id == content.id, PostLike.user_id == user.id
        )
    ) is not None

    await session.execute(
        insert(PostLike)
        .values(post_id=content.id, user_id=user.id)
        .on_conflict_do_nothing(constraint="uq_post_like_post_user")
    )

    # Token economy: reward content author for receiving a like (not self-likes, first-time only)
    if content.author_id != user.id and not already_liked:
        like_reward = await token_service.get_param(session, "like_reward")
        await token_service.earn(session, content.author_id, like_reward, "post_liked", post_id)

    await session.commit()
    state = await _post_like_state(session, post_id, user.id)
    root_type = "post" if content.type == "post" else "patch" if content.patch_id else "post"
    root_id = content.id if content.type == "post" else content.patch_id or content.parent_id
    if root_id and content_is_public(content):
        await publish_feed_event(
            "updated",
            item_type=root_type,
            item_id=str(root_id),
        )
    return state


@router.delete("/{post_id}/like", response_model=PostLikeRead)
async def unlike_post(
    post_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Remove the current user's like. Repeated requests are idempotent."""
    content = await session.scalar(
        select(ContentModel).where(
            ContentModel.id == post_id, ContentModel.type.in_(("post", "comment"))
        )
    )
    await require_content_visible(content, user, session)

    await session.execute(
        delete(PostLike).where(
            PostLike.post_id == content.id, PostLike.user_id == user.id
        )
    )
    await session.commit()
    state = await _post_like_state(session, post_id, user.id)
    root_type = "post" if content.type == "post" else "patch" if content.patch_id else "post"
    root_id = content.id if content.type == "post" else content.patch_id or content.parent_id
    if root_id and content_is_public(content):
        await publish_feed_event(
            "updated",
            item_type=root_type,
            item_id=str(root_id),
        )
    return state


@router.delete("/{content_id}", status_code=204)
async def delete_content(
    content_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Delete own content (post or comment)."""
    stmt = (
        select(ContentModel.id)
        .where(ContentModel.id == content_id)
        .with_for_update()
    )
    locked_content_id = await session.scalar(stmt)
    content = (
        await session.scalar(
            select(ContentModel).where(ContentModel.id == locked_content_id)
        )
        if locked_content_id is not None
        else None
    )
    await require_content_visible(content, user, session)
    if content.author_id != user.id:
        raise HTTPException(status_code=403, detail="FORBIDDEN")
    if content.revision_number > 1:
        raise HTTPException(
            status_code=409,
            detail="AUDITED_CONTENT_DELETE_LOCKED",
        )
    if content.type == "post" and await session.scalar(
        select(PostPoll.id).where(PostPoll.post_id == content.id)
    ):
        raise HTTPException(
            status_code=409,
            detail="POLL_CONTENT_DELETE_LOCKED",
        )

    if content.type == "post":
        root_type = "post"
        root_id = content.id
    elif content.patch_id:
        root_type = "patch"
        root_id = content.patch_id
    else:
        root_type = "post"
        root_id = content.parent_id

    was_public = content_is_public(content)
    await session.delete(content)
    await session.commit()
    if root_id and was_public:
        await publish_feed_event(
            "removed" if content.type == "post" else "updated",
            item_type=root_type,
            item_id=str(root_id),
        )


# ── Content promotion boost ──

_BOOST_TIERS: dict[str, tuple[str, float]] = {
    "low": ("boost_price_low", 1.25),
    "mid": ("boost_price_mid", 1.6),
    "high": ("boost_price_high", 2.0),
}


@router.post("/{post_id}/boost", status_code=201)
async def boost_post(
    post_id: UUID,
    data: ContentBoostCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Promote a post for 24 hours by spending AGC."""
    if data.tier not in _BOOST_TIERS:
        raise HTTPException(status_code=422, detail="INVALID_BOOST_TIER")

    content = await session.scalar(
        select(ContentModel).where(
            ContentModel.id == post_id, ContentModel.type == "post"
        )
    )
    if not content:
        raise HTTPException(status_code=404, detail="POST_NOT_FOUND")
    if content.author_id != user.id:
        raise HTTPException(status_code=403, detail="FORBIDDEN")

    now = datetime.now(timezone.utc)
    active = await session.scalar(
        select(ContentBoost.id).where(
            ContentBoost.content_id == post_id,
            ContentBoost.expires_at > now,
        )
    )
    if active:
        raise HTTPException(status_code=409, detail="BOOST_ALREADY_ACTIVE")

    price_param, weight = _BOOST_TIERS[data.tier]
    price = await token_service.get_param(session, price_param)

    try:
        await token_service.spend(session, user.id, price, "content_boost", post_id)
    except ValueError:
        raise HTTPException(
            status_code=402, detail=f"INSUFFICIENT_AGC_NEED_{price}"
        )

    boost = ContentBoost(
        content_id=post_id,
        tier=data.tier,
        weight=weight,
        expires_at=now + timedelta(hours=24),
    )
    session.add(boost)
    await session.commit()

    await publish_feed_event(
        "updated",
        item_type="post",
        item_id=str(post_id),
    )

    return {
        "ok": True,
        "tier": data.tier,
        "weight": weight,
        "expires_at": boost.expires_at.isoformat(),
        "balance_after": (await token_service.get_balance(session, user.id)).balance,
    }


# ── Comments (nested under posts) ──


@router.get("/{post_id}/comments", response_model=list[CommentRead])
async def list_comments(
    post_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(optional_current_user),
):
    """List comments for a post, flat with replying_id markers."""
    allow_staff = bool(user and user.role in ("moderator", "super_admin"))
    # Verify post exists
    post_stmt = select(ContentModel).where(
        ContentModel.id == post_id, ContentModel.type == "post"
    )
    post_result = await session.execute(post_stmt)
    post = post_result.scalar_one_or_none()
    try:
        await require_content_visible(
            post,
            user,
            session,
            allow_staff=allow_staff,
        )
    except HTTPException as error:
        if error.detail == "CONTENT_NOT_FOUND":
            raise HTTPException(status_code=404, detail="POST_NOT_FOUND") from error
        raise

    # Fetch comments
    stmt = (
        select(ContentModel)
        .where(
            ContentModel.parent_id == post_id,
            ContentModel.type == "comment",
            content_tree_visibility_clause(user, allow_staff=allow_staff),
        )
        .order_by(ContentModel.created_at.asc())
    )
    result = await session.execute(stmt)
    comments = result.scalars().all()

    # Build traceability, reply counts and reaction state in batches.
    replying_ids = [c.replying_id for c in comments if c.replying_id]
    usernames = {}
    reply_content = {}
    if replying_ids:
        user_stmt = select(ContentModel.id, User.username, ContentModel.content).join(
            User, ContentModel.author_id == User.id
        ).where(
            ContentModel.id.in_(replying_ids),
            content_visibility_clause(user, allow_staff=allow_staff),
        )
        user_result = await session.execute(user_stmt)
        rows = user_result.all()
        usernames = {str(row[0]): row[1] for row in rows}
        reply_content = {str(row[0]): row[2] for row in rows}

    comment_ids = [c.id for c in comments]
    reply_counts = {}
    like_counts = {}
    liked_ids = set()
    if comment_ids:
        reply_counts = dict(
            (
                await session.execute(
                    select(ContentModel.replying_id, func.count(ContentModel.id))
                    .where(
                        ContentModel.replying_id.in_(comment_ids),
                        content_visibility_clause(user, allow_staff=allow_staff),
                    )
                    .group_by(ContentModel.replying_id)
                )
            ).all()
        )
        like_counts = dict(
            (
                await session.execute(
                    select(PostLike.post_id, func.count(PostLike.id))
                    .where(PostLike.post_id.in_(comment_ids))
                    .group_by(PostLike.post_id)
                )
            ).all()
        )
        if user:
            liked_ids = set(
                (
                    await session.execute(
                        select(PostLike.post_id).where(
                            PostLike.post_id.in_(comment_ids),
                            PostLike.user_id == user.id,
                        )
                    )
                ).scalars()
            )

    return [
        CommentRead(
            id=c.id,
            content=c.content,
            author_id=c.author_id,
            parent_id=c.parent_id or post_id,
            replying_id=c.replying_id,
            author_username=c.author.username,
            replying_to_username=usernames.get(str(c.replying_id)) if c.replying_id else None,
            replying_to_content=reply_content.get(str(c.replying_id)) if c.replying_id else None,
            reply_count=reply_counts.get(c.id, 0),
            like_count=like_counts.get(c.id, 0),
            liked_by_me=c.id in liked_ids,
            **moderation_metadata_for(c, user, allow_staff=allow_staff),
            revision_number=c.revision_number,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in comments
    ]


@router.post("/{post_id}/comments", response_model=CommentRead, status_code=201)
async def create_comment(
    post_id: UUID,
    data: CommentCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Reply to a post, optionally mention which comment you're replying to."""
    await check_not_banned(user.id, session, "mute_post")
    # Verify post exists
    post_stmt = select(ContentModel).where(
        ContentModel.id == post_id, ContentModel.type == "post"
    )
    post_result = await session.execute(post_stmt)
    post = post_result.scalar_one_or_none()
    try:
        post = await require_content_interactable(post, user, session)
    except HTTPException as error:
        if error.detail == "CONTENT_NOT_FOUND":
            raise HTTPException(status_code=404, detail="POST_NOT_FOUND") from error
        raise

    if not data.content.strip():
        raise HTTPException(status_code=422, detail="Content is required")

    # If replying to a specific comment, verify it exists
    if data.replying_id:
        reply_stmt = select(ContentModel).where(
            ContentModel.id == data.replying_id,
            ContentModel.type == "comment",
            ContentModel.parent_id == post.id,
        )
        reply_result = await session.execute(reply_stmt)
        reply_target = reply_result.scalar_one_or_none()
        if not reply_target:
            raise HTTPException(status_code=404, detail="REPLY_TARGET_NOT_FOUND")
        try:
            await require_content_interactable(reply_target, user, session)
        except HTTPException as error:
            if error.detail == "CONTENT_NOT_FOUND":
                raise HTTPException(
                    status_code=404,
                    detail="REPLY_TARGET_NOT_FOUND",
                ) from error
            raise

    moderation = await assess_content_moderation_after_read(
        session,
        data.content,
    )

    # Recheck the target tree after the external call, holding the relevant
    # rows until the new comment is committed.
    await check_not_banned(user.id, session, "mute_post")
    locked_post_id = await session.scalar(
        select(ContentModel.id)
        .where(ContentModel.id == post_id, ContentModel.type == "post")
        .with_for_update()
    )
    if locked_post_id is None:
        raise HTTPException(status_code=404, detail="POST_NOT_FOUND")
    post = await session.scalar(
        select(ContentModel)
        .where(ContentModel.id == locked_post_id)
        .execution_options(populate_existing=True)
    )
    try:
        post = await require_content_interactable(post, user, session)
    except HTTPException as error:
        if error.detail == "CONTENT_NOT_FOUND":
            raise HTTPException(status_code=404, detail="POST_NOT_FOUND") from error
        raise

    if data.replying_id:
        locked_reply_id = await session.scalar(
            select(ContentModel.id)
            .where(
                ContentModel.id == data.replying_id,
                ContentModel.type == "comment",
                ContentModel.parent_id == post.id,
            )
            .with_for_update()
        )
        if locked_reply_id is None:
            raise HTTPException(status_code=404, detail="REPLY_TARGET_NOT_FOUND")
        reply_target = await session.scalar(
            select(ContentModel)
            .where(ContentModel.id == locked_reply_id)
            .execution_options(populate_existing=True)
        )
        try:
            await require_content_interactable(reply_target, user, session)
        except HTTPException as error:
            if error.detail == "CONTENT_NOT_FOUND":
                raise HTTPException(
                    status_code=404,
                    detail="REPLY_TARGET_NOT_FOUND",
                ) from error
            raise

    comment = ContentModel(
        type="comment",
        content=data.content.strip(),
        parent_id=post.id,
        replying_id=data.replying_id,
        author_id=user.id,
        moderation_status=moderation.status,
        moderation_reason=moderation.reason,
        published_at=(
            datetime.now(timezone.utc)
            if moderation.status == "published"
            else None
        ),
    )
    session.add(comment)
    await session.commit()
    await session.refresh(comment)

    # ── Notifications ──
    if comment.moderation_status == "pending_review":
        await notify_content_pending(comment)
    else:
        await announce_content_published(comment, session=session)
    return CommentRead(
        id=comment.id,
        content=comment.content,
        author_id=comment.author_id,
        parent_id=comment.parent_id or post_id,
        replying_id=comment.replying_id,
        author_username=comment.author.username,
        replying_to_username=None,
        replying_to_content=None,
        **moderation_metadata_for(comment, user),
        revision_number=comment.revision_number,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )
