from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_users.password import PasswordHelper

from app.db import get_session
from app.db.models.content import Content as ContentModel
from app.db.models.patch import Patch as PatchModel
from app.db.models.follow import Follow
from app.db.models.post_like import PostLike
from app.schemas.post import PostRead
from app.schemas.patch import PatchRead
from app.schemas.user import (
    FollowState,
    UserContentItem,
    UserPublic,
    UserRead,
    UserUpdate,
)
from app.db.models.user import User, get_user_db
from .deps import current_user, optional_current_user

router = APIRouter()
password_helper = PasswordHelper()


async def _follow_state(
    session: AsyncSession, target_id: UUID, viewer_id: UUID | None
) -> FollowState:
    follower_count = await session.scalar(
        select(func.count(Follow.id)).where(Follow.following_id == target_id)
    )
    following_count = await session.scalar(
        select(func.count(Follow.id)).where(Follow.follower_id == target_id)
    )
    is_following = False
    if viewer_id:
        is_following = bool(
            await session.scalar(
                select(Follow.id).where(
                    Follow.follower_id == viewer_id,
                    Follow.following_id == target_id,
                )
            )
        )
    return FollowState(
        follower_count=follower_count or 0,
        following_count=following_count or 0,
        is_following=is_following,
    )


@router.get("/me", response_model=UserRead)
async def get_me(user: User = Depends(current_user)) -> UserRead:
    """Return the currently authenticated user."""
    return UserRead.model_validate(user)


@router.patch("/me", response_model=UserRead)
async def update_me(
    data: UserUpdate,
    user_db=Depends(get_user_db),
    user: User = Depends(current_user),
) -> UserRead:
    """Update the currently authenticated user's profile."""
    update_dict = data.model_dump(exclude_unset=True, exclude_none=True)

    if not update_dict:
        raise HTTPException(status_code=400, detail="UPDATE_NO_FIELDS")

    if "password" in update_dict:
        if len(update_dict["password"]) < 8:
            raise HTTPException(status_code=422, detail="UPDATE_PASSWORD_TOO_SHORT")
        update_dict["hashed_password"] = password_helper.hash(
            update_dict.pop("password")
        )

    if "email" in update_dict and update_dict["email"] != user.email:
        existing = await user_db.get_by_email(update_dict["email"])
        if existing:
            raise HTTPException(status_code=409, detail="UPDATE_EMAIL_TAKEN")

    if "username" in update_dict and update_dict["username"] != user.username:
        existing = await user_db.session.execute(
            select(User).where(User.username == update_dict["username"])
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="UPDATE_USERNAME_TAKEN")

    updated_user: User = await user_db.update(user, update_dict)
    return UserRead.model_validate(updated_user)


# ── Public user profile ──


@router.get("/{user_id}/posts", response_model=list[PostRead])
async def list_user_posts(
    user_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """List posts by a specific user."""
    offset = (page - 1) * page_size

    stmt = (
        select(ContentModel)
        .where(ContentModel.author_id == user_id, ContentModel.type == "post")
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


@router.get("/{user_id}/patches", response_model=list[PatchRead])
async def list_user_patches(
    user_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """List patches by a specific user."""
    from app.db.models.vote import Vote as VoteModel

    offset = (page - 1) * page_size

    stmt = (
        select(PatchModel)
        .where(PatchModel.author_id == user_id)
        .order_by(PatchModel.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    patches = result.scalars().all()

    # Get vote counts
    patch_ids = [str(p.id) for p in patches]
    counts_map: dict = {}
    if patch_ids:
        rows = (
            await session.execute(
                select(VoteModel.patch_id, VoteModel.choice, func.count(VoteModel.id))
                .where(VoteModel.patch_id.in_(patch_ids))
                .group_by(VoteModel.patch_id, VoteModel.choice)
            )
        ).all()
        for pid, choice, cnt in rows:
            key = str(pid)
            if key not in counts_map:
                counts_map[key] = {"for": 0, "against": 0, "abstain": 0}
            counts_map[key][choice] = cnt

    return [
        PatchRead(
            id=p.id,
            title=p.title,
            content=p.content,
            pr_number=p.pr_number,
            status=p.status,
            author_id=p.author_id,
            author_username=p.author.username,
            voting_ends_at=p.voting_ends_at,
            for_count=counts_map.get(str(p.id), {}).get("for", 0),
            against_count=counts_map.get(str(p.id), {}).get("against", 0),
            abstain_count=counts_map.get(str(p.id), {}).get("abstain", 0),
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in patches
    ]


@router.put("/{user_id}/follow", response_model=FollowState)
async def follow_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    if user_id == user.id:
        raise HTTPException(status_code=422, detail="CANNOT_FOLLOW_SELF")
    if not await session.scalar(select(User.id).where(User.id == user_id)):
        raise HTTPException(status_code=404, detail="USER_NOT_FOUND")

    await session.execute(
        insert(Follow)
        .values(follower_id=user.id, following_id=user_id)
        .on_conflict_do_nothing(constraint="uq_follow_pair")
    )
    await session.commit()
    return await _follow_state(session, user_id, user.id)


@router.delete("/{user_id}/follow", response_model=FollowState)
async def unfollow_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    if not await session.scalar(select(User.id).where(User.id == user_id)):
        raise HTTPException(status_code=404, detail="USER_NOT_FOUND")
    await session.execute(
        delete(Follow).where(
            Follow.follower_id == user.id, Follow.following_id == user_id
        )
    )
    await session.commit()
    return await _follow_state(session, user_id, user.id)


@router.get("/{user_id}/content", response_model=list[UserContentItem])
async def list_user_content(
    user_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    viewer: User | None = Depends(optional_current_user),
):
    """Unified public activity: posts, patch proposals and replies."""
    if not await session.scalar(select(User.id).where(User.id == user_id)):
        raise HTTPException(status_code=404, detail="USER_NOT_FOUND")

    contents = (
        await session.execute(
            select(ContentModel)
            .where(ContentModel.author_id == user_id)
            .order_by(ContentModel.created_at.desc())
            .limit(1000)
        )
    ).scalars().all()
    patches = (
        await session.execute(
            select(PatchModel)
            .where(PatchModel.author_id == user_id)
            .order_by(PatchModel.created_at.desc())
            .limit(1000)
        )
    ).scalars().all()

    content_ids = [item.id for item in contents]
    replying_ids = [item.replying_id for item in contents if item.replying_id]
    post_ids = [item.parent_id for item in contents if item.parent_id]
    patch_ids = [item.patch_id for item in contents if item.patch_id]

    reply_counts = {}
    post_reply_counts = {}
    like_counts = {}
    if content_ids:
        reply_counts = dict(
            (
                await session.execute(
                    select(ContentModel.replying_id, func.count(ContentModel.id))
                    .where(ContentModel.replying_id.in_(content_ids))
                    .group_by(ContentModel.replying_id)
                )
            ).all()
        )
        post_reply_counts = dict(
            (
                await session.execute(
                    select(ContentModel.parent_id, func.count(ContentModel.id))
                    .where(ContentModel.parent_id.in_(content_ids))
                    .group_by(ContentModel.parent_id)
                )
            ).all()
        )
        like_counts = dict(
            (
                await session.execute(
                    select(PostLike.post_id, func.count(PostLike.id))
                    .where(PostLike.post_id.in_(content_ids))
                    .group_by(PostLike.post_id)
                )
            ).all()
        )

    trace_map = {}
    if replying_ids:
        trace_map = {
            row[0]: (row[1], row[2])
            for row in (
                await session.execute(
                    select(ContentModel.id, User.username, ContentModel.content)
                    .join(User, ContentModel.author_id == User.id)
                    .where(ContentModel.id.in_(replying_ids))
                )
            ).all()
        }
    post_map = {}
    if post_ids:
        post_map = dict(
            (
                await session.execute(
                    select(ContentModel.id, ContentModel.title).where(
                        ContentModel.id.in_(post_ids)
                    )
                )
            ).all()
        )
    patch_map = {}
    if patch_ids:
        patch_map = dict(
            (
                await session.execute(
                    select(PatchModel.id, PatchModel.title).where(
                        PatchModel.id.in_(patch_ids)
                    )
                )
            ).all()
        )

    items: list[UserContentItem] = []
    for item in contents:
        root_type = "post" if item.parent_id else "patch" if item.patch_id else None
        root_id = item.parent_id or item.patch_id
        root_title = (
            post_map.get(item.parent_id)
            if item.parent_id
            else patch_map.get(item.patch_id)
        )
        trace = trace_map.get(item.replying_id)
        items.append(
            UserContentItem(
                id=item.id,
                type=item.type,
                title=item.title,
                content=item.content,
                created_at=item.created_at,
                root_type=root_type,
                root_id=root_id,
                root_title=root_title,
                replying_to_id=item.replying_id,
                replying_to_username=trace[0] if trace else None,
                replying_to_content=trace[1] if trace else None,
                reply_count=(
                    post_reply_counts.get(item.id, 0)
                    if item.type == "post"
                    else reply_counts.get(item.id, 0)
                ),
                like_count=like_counts.get(item.id, 0),
                can_delete=bool(viewer and viewer.id == item.author_id),
            )
        )
    profile_patch_ids = [patch.id for patch in patches]
    patch_comment_counts = {}
    if profile_patch_ids:
        patch_comment_counts = dict(
            (
                await session.execute(
                    select(ContentModel.patch_id, func.count(ContentModel.id))
                    .where(ContentModel.patch_id.in_(profile_patch_ids))
                    .group_by(ContentModel.patch_id)
                )
            ).all()
        )
    for patch in patches:
        items.append(
            UserContentItem(
                id=patch.id,
                type="patch",
                title=patch.title,
                content=patch.content,
                created_at=patch.created_at,
                pr_number=patch.pr_number,
                status=patch.status,
                reply_count=patch_comment_counts.get(patch.id, 0),
                can_delete=bool(
                    viewer and viewer.id == patch.author_id and patch.status == "draft"
                ),
            )
        )

    items.sort(key=lambda item: item.created_at, reverse=True)
    offset = (page - 1) * page_size
    return items[offset : offset + page_size]


@router.get("/{user_id}", response_model=UserPublic)
async def get_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    viewer: User | None = Depends(optional_current_user),
):
    """Get a user's public profile."""
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="USER_NOT_FOUND")
    follow = await _follow_state(session, user.id, viewer.id if viewer else None)
    return UserPublic(
        id=user.id,
        username=user.username,
        nickname=user.nickname,
        bio=user.bio,
        **follow.model_dump(),
    )
