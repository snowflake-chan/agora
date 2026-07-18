from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.db.models.content import Content as ContentModel
from app.db.models.patch import Patch as PatchModel
from app.db.models.user import User
from app.schemas.post import (
    CommentCreate,
    CommentRead,
    FeedItem,
    PostCreate,
    PostRead,
    PostUpdate,
)
from app.users.deps import current_user

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

    return [
        PostRead(
            id=p.id,
            title=p.title or "",
            content=p.content,
            author_id=p.author_id,
            tags=p.tags,
            author_username=p.author.username,
            reply_count=counts.get(p.id, 0),
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
    session: AsyncSession = Depends(get_session),
):
    """Unified feed of posts and patches, newest first."""
    offset = (page - 1) * page_size

    # Fetch recent posts
    posts = (
        await session.execute(
            select(ContentModel)
            .where(ContentModel.type == "post")
            .order_by(ContentModel.created_at.desc())
            .limit(1000)
        )
    ).scalars().all()

    # Fetch recent patches
    patches = (
        await session.execute(
            select(PatchModel)
            .order_by(PatchModel.created_at.desc())
            .limit(1000)
        )
    ).scalars().all()

    # Merge & sort by created_at desc
    items: list[FeedItem] = []

    for p in posts:
        items.append(FeedItem(
            id=p.id, type="post", title=p.title or "", content=p.content,
            author_id=p.author_id, author_username=p.author.username,
            created_at=p.created_at, tags=p.tags, reply_count=0,
        ))

    for p in patches:
        items.append(FeedItem(
            id=p.id, type="patch", title=p.title, content=p.content,
            author_id=p.author_id, author_username=p.author.username,
            created_at=p.created_at,
            pr_number=p.pr_number, status=p.status,
        ))

    items.sort(key=lambda x: x.created_at, reverse=True)
    return items[offset:offset + page_size]


@router.get("/{post_id}", response_model=PostRead)
async def get_post(
    post_id: str,
    session: AsyncSession = Depends(get_session),
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

    return PostRead(
        id=post.id,
        title=post.title or "",
        content=post.content,
        author_id=post.author_id,
        tags=post.tags,
        author_username=post.author.username,
        reply_count=reply_count or 0,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


@router.delete("/{content_id}", status_code=204)
async def delete_content(
    content_id: str,
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

    await session.delete(content)
    await session.commit()


# ── Comments (nested under posts) ──


@router.get("/{post_id}/comments", response_model=list[CommentRead])
async def list_comments(
    post_id: str,
    session: AsyncSession = Depends(get_session),
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

    # Build lookup for replying_to usernames
    replying_ids = [c.replying_id for c in comments if c.replying_id]
    usernames = {}
    if replying_ids:
        user_stmt = select(ContentModel.id, User.username).join(
            User, ContentModel.author_id == User.id
        ).where(ContentModel.id.in_(replying_ids))
        user_result = await session.execute(user_stmt)
        usernames = {str(row[0]): row[1] for row in user_result}

    return [
        CommentRead(
            id=c.id,
            content=c.content,
            author_id=c.author_id,
            parent_id=c.parent_id or post_id,
            replying_id=c.replying_id,
            author_username=c.author.username,
            replying_to_username=usernames.get(str(c.replying_id)) if c.replying_id else None,
            created_at=c.created_at,
        )
        for c in comments
    ]


@router.post("/{post_id}/comments", response_model=CommentRead, status_code=201)
async def create_comment(
    post_id: str,
    data: CommentCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Reply to a post, optionally mention which comment you're replying to."""
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

    return CommentRead(
        id=comment.id,
        content=comment.content,
        author_id=comment.author_id,
        parent_id=comment.parent_id or post_id,
        replying_id=comment.replying_id,
        author_username=comment.author.username,
        replying_to_username=None,
        created_at=comment.created_at,
    )
