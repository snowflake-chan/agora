from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_users.password import PasswordHelper

from app.db import get_session
from app.db.models.content import Content as ContentModel
from app.db.models.patch import Patch as PatchModel
from app.schemas.post import PostRead
from app.schemas.patch import PatchRead
from app.schemas.user import UserPublic, UserRead, UserUpdate
from app.db.models.user import User, get_user_db
from .deps import current_user

router = APIRouter()
password_helper = PasswordHelper()


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


@router.get("/{user_id}", response_model=UserPublic)
async def get_user(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get a user's public profile."""
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="USER_NOT_FOUND")
    return UserPublic.model_validate(user)
