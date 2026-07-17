from fastapi import APIRouter, Depends, HTTPException
from fastapi_users.password import PasswordHelper

from app.schemas.user import UserRead, UserUpdate
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
    """Update the currently authenticated user's email or password."""
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

    updated_user: User = await user_db.update(user, update_dict)
    return UserRead.model_validate(updated_user)
