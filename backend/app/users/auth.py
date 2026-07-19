from sqlalchemy import select

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi_users.authentication import Strategy
from fastapi_users.password import PasswordHelper

from app.config import settings
from app.schemas.user import LoginRequest, UserCreate, UserRead
from app.db.models.user import User, get_user_db
from app.users.backend import auth_backend, transport as cookie_transport
from app.users.rate_limit import client_ip, enforce_rate_limit

router = APIRouter()
password_helper = PasswordHelper()


def _set_auth_cookie(response: Response, token: str) -> None:
    """Set the JWT cookie with every policy configured by CookieTransport."""
    response.set_cookie(
        key=cookie_transport.cookie_name,
        value=token,
        max_age=cookie_transport.cookie_max_age,
        path=cookie_transport.cookie_path,
        domain=cookie_transport.cookie_domain,
        secure=cookie_transport.cookie_secure,
        httponly=cookie_transport.cookie_httponly,
        samesite=cookie_transport.cookie_samesite,
    )


def _delete_auth_cookie(response: Response) -> None:
    """Expire the JWT cookie using the same scope and security attributes."""
    response.delete_cookie(
        key=cookie_transport.cookie_name,
        path=cookie_transport.cookie_path,
        domain=cookie_transport.cookie_domain,
        secure=cookie_transport.cookie_secure,
        httponly=cookie_transport.cookie_httponly,
        samesite=cookie_transport.cookie_samesite,
    )


@router.post("/register", response_model=UserRead)
async def register(
    data: UserCreate,
    request: Request,
    response: Response,
    user_db=Depends(get_user_db),
    strategy: Strategy = Depends(auth_backend.get_strategy),
) -> UserRead:
    """Register a new user and auto-login with a cookie."""
    await enforce_rate_limit(
        scope="register",
        identifier=client_ip(request),
        limit=settings.AUTH_REGISTER_ATTEMPTS,
        window_seconds=settings.AUTH_REGISTER_WINDOW_SECONDS,
    )

    existing = await user_db.get_by_email(data.email)
    if existing:
        raise HTTPException(status_code=409, detail="REGISTER_EMAIL_TAKEN")

    existing_username = await user_db.session.execute(
        select(User).where(User.username == data.username)
    )
    if existing_username.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="REGISTER_USERNAME_TAKEN")

    if len(data.password) < 8:
        raise HTTPException(status_code=422, detail="REGISTER_PASSWORD_TOO_SHORT")

    user: User = await user_db.create(
        {
            "email": data.email,
            "username": data.username,
            "hashed_password": password_helper.hash(data.password),
            "is_active": True,
            "is_superuser": False,
            "is_verified": False,
        }
    )

    token = await strategy.write_token(user)
    _set_auth_cookie(response, token)

    return UserRead.model_validate(user)


@router.post("/login", response_model=UserRead)
async def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    user_db=Depends(get_user_db),
    strategy: Strategy = Depends(auth_backend.get_strategy),
) -> UserRead:
    """Authenticate with email & password, set session cookie."""
    await enforce_rate_limit(
        scope="login",
        identifier=data.email.strip().lower(),
        limit=settings.AUTH_LOGIN_ATTEMPTS,
        window_seconds=settings.AUTH_LOGIN_WINDOW_SECONDS,
    )

    user: User | None = await user_db.get_by_email(data.email)
    if not user:
        raise HTTPException(status_code=401, detail="LOGIN_INVALID_CREDENTIALS")

    verified, new_hash = password_helper.verify_and_update(
        data.password, user.hashed_password
    )
    if not verified:
        raise HTTPException(status_code=401, detail="LOGIN_INVALID_CREDENTIALS")
    if new_hash:
        await user_db.update(user, {"hashed_password": new_hash})

    token = await strategy.write_token(user)
    _set_auth_cookie(response, token)

    return UserRead.model_validate(user)


@router.post("/logout", status_code=204)
async def logout(response: Response) -> None:
    """Clear the session cookie."""
    _delete_auth_cookie(response)
