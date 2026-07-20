import asyncio
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.db import get_session
from app.db.models.content import Content as ContentModel
from app.db.models.follow import Follow
from app.db.models.patch import Patch as PatchModel
from app.db.models.post_like import PostLike
from app.db.models.user import User
from app.db.models.vote import Vote as VoteModel
from app.deps import check_not_banned, require_content_visible
from app.notifications.service import create_notification, notify_followers
from app.notifications.redis import get_redis
from app.posts.feed import FeedMode, rank_feed_items
from app.posts.realtime import FEED_CHANNEL, publish_feed_event
from app.schemas.post import (
    CommentCreate,
    CommentRead,
    FeedItem,
    PostCreate,
    PostLikeRead,
    PostRead,
)
from app.users.deps import current_user, optional_current_user

router = APIRouter()


# ── Posts ──


@router.get("", response_model=list[PostRead])
async def list_posts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """List posts (type=post), newest first."""
    offset = (page - 1) * page_size

    # Count total
    total = await session.scalar(
        select(func.count(ContentModel.id)).where(ContentModel.type == "post")
    )

    # Fetch posts with author
    stmt = (
        select(ContentModel)
        .where(ContentModel.type == "post")
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

    post = ContentModel(
        type="post",
        title=data.title.strip(),
        content=data.content.strip(),
        tags=data.tags,
        author_id=user.id,
    )
    session.add(post)
    await session.commit()
    await session.refresh(post)

    # Eagerly load author
    stmt = select(ContentModel).where(ContentModel.id == post.id)
    result = await session.execute(stmt)
    post = result.scalar_one()

    await publish_feed_event(
        "created",
        item_type="post",
        item_id=str(post.id),
    )
    await notify_followers(
        author_id=user.id,
        type="following_post",
        title=f"{user.nickname or user.username} published a new post",
        message=post.title or "",
        link=f"/posts/{post.id}",
    )

    return PostRead(
        id=post.id,
        title=post.title or "",
        content=post.content,
        author_id=post.author_id,
        tags=post.tags,
        author_username=post.author.username,
        reply_count=0,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


# ── Feed (unified timeline) ──


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
                )
                .order_by(ContentModel.created_at.desc())
                .limit(50)
            )
        ).scalars().all()
        for tags in [*authored_tags, *liked_tags]:
            interest_tags.update(tag.casefold() for tag in tags or [])

    # Fetch a bounded candidate pool; ranking happens after all signals are attached.
    posts = (
        await session.execute(
            select(ContentModel)
            .where(ContentModel.type == "post")
            .order_by(ContentModel.created_at.desc())
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
    if post_ids:
        count_stmt = (
            select(ContentModel.parent_id, func.count(ContentModel.id))
            .where(
                ContentModel.parent_id.in_(post_ids),
                ContentModel.type == "comment",
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
        items.append(FeedItem(
            id=p.id, type="post", title=p.title or "", content=p.content,
            author_id=p.author_id, author_username=p.author.username,
            created_at=p.created_at, tags=p.tags, reply_count=reply_counts.get(p.id, 0),
            like_count=like_counts.get(p.id, 0),
        ))

    for p in patches:
        voting_ends_at = p.voting_ends_at
        if voting_ends_at is None and p.status == "voting" and p.created_at:
            voting_ends_at = p.created_at + timedelta(days=3)
        items.append(FeedItem(
            id=p.id, type="patch", title=p.title, content=p.content,
            author_id=p.author_id, author_username=p.author.username,
            created_at=p.created_at,
            pr_number=p.pr_number, status=p.status,
            voting_ends_at=voting_ends_at,
            reply_count=patch_comment_counts.get(p.id, 0),
            for_count=vote_counts.get(str(p.id), {}).get("for", 0),
            against_count=vote_counts.get(str(p.id), {}).get("against", 0),
            abstain_count=vote_counts.get(str(p.id), {}).get("abstain", 0),
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
    stmt = select(ContentModel).where(
        ContentModel.id == post_id, ContentModel.type == "post"
    )
    result = await session.execute(stmt)
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="POST_NOT_FOUND")

    # Count replies
    reply_count = await session.scalar(
        select(func.count(ContentModel.id)).where(
            ContentModel.parent_id == post.id, ContentModel.type == "comment"
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
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


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
    if not content:
        raise HTTPException(status_code=404, detail="CONTENT_NOT_FOUND")
    await require_content_visible(content, user, session)

    await session.execute(
        insert(PostLike)
        .values(post_id=content.id, user_id=user.id)
        .on_conflict_do_nothing(constraint="uq_post_like_post_user")
    )
    await session.commit()
    state = await _post_like_state(session, post_id, user.id)
    root_type = "post" if content.type == "post" else "patch" if content.patch_id else "post"
    root_id = content.id if content.type == "post" else content.patch_id or content.parent_id
    if root_id:
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
    if not content:
        raise HTTPException(status_code=404, detail="CONTENT_NOT_FOUND")
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
    if root_id:
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
    stmt = select(ContentModel).where(ContentModel.id == content_id)
    result = await session.execute(stmt)
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=404, detail="CONTENT_NOT_FOUND")
    if content.author_id != user.id:
        raise HTTPException(status_code=403, detail="FORBIDDEN")

    if content.type == "post":
        root_type = "post"
        root_id = content.id
    elif content.patch_id:
        root_type = "patch"
        root_id = content.patch_id
    else:
        root_type = "post"
        root_id = content.parent_id

    await session.delete(content)
    await session.commit()
    if root_id:
        await publish_feed_event(
            "removed" if content.type == "post" else "updated",
            item_type=root_type,
            item_id=str(root_id),
        )


# ── Comments (nested under posts) ──


@router.get("/{post_id}/comments", response_model=list[CommentRead])
async def list_comments(
    post_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(optional_current_user),
):
    """List comments for a post, flat with replying_id markers."""
    # Verify post exists
    post_stmt = select(ContentModel).where(
        ContentModel.id == post_id, ContentModel.type == "post"
    )
    post_result = await session.execute(post_stmt)
    if not post_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="POST_NOT_FOUND")

    # Fetch comments
    stmt = (
        select(ContentModel)
        .where(
            ContentModel.parent_id == post_id,
            ContentModel.type == "comment",
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
        ).where(ContentModel.id.in_(replying_ids))
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
                    .where(ContentModel.replying_id.in_(comment_ids))
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
            created_at=c.created_at,
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
    if not post:
        raise HTTPException(status_code=404, detail="POST_NOT_FOUND")

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
        if not reply_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="REPLY_TARGET_NOT_FOUND")

    comment = ContentModel(
        type="comment",
        content=data.content.strip(),
        parent_id=post.id,
        replying_id=data.replying_id,
        author_id=user.id,
    )
    session.add(comment)
    await session.commit()
    await session.refresh(comment)

    # ── Notifications ──
    # Notify post author (unless commenting on your own post)
    if post.author_id != user.id:
        await create_notification(
            recipient_id=post.author_id,
            type="reply",
            title="New reply",
            message=f"{user.nickname or user.username} replied to your post \"{post.title or ''}\"",
            link=f"/posts/{post.id}#{comment.id}",
        )

    # Notify replied-to comment author (if replying to a specific comment)
    if data.replying_id:
        reply_stmt = select(ContentModel.author_id).where(
            ContentModel.id == data.replying_id
        )
        reply_author_id = await session.scalar(reply_stmt)
        if reply_author_id and reply_author_id != user.id:
            await create_notification(
                recipient_id=reply_author_id,
                type="reply",
                title="New reply",
                message=f"{user.nickname or user.username} replied to your comment",
                link=f"/posts/{post.id}#{comment.id}",
            )

    await publish_feed_event(
        "updated",
        item_type="post",
        item_id=str(post.id),
    )
    return CommentRead(
        id=comment.id,
        content=comment.content,
        author_id=comment.author_id,
        parent_id=comment.parent_id or post_id,
        replying_id=comment.replying_id,
        author_username=comment.author.username,
        replying_to_username=None,
        replying_to_content=None,
        created_at=comment.created_at,
    )
