from fastapi import Depends
from fastapi_users.authentication import AuthenticationBackend
from fastapi_users.authentication import CookieTransport
from fastapi_users.authentication.strategy.db import DatabaseStrategy

from app.config import settings
from app.users.sessions import LimitedAccessTokenDatabase, get_access_token_db


def cookie_secure() -> bool:
    return settings.COOKIE_SECURE and (
        settings.is_production()
        or settings.PUBLIC_SITE_URL.lower().startswith("https://")
    )


def get_strategy(
    database: LimitedAccessTokenDatabase = Depends(get_access_token_db),
) -> DatabaseStrategy:
    return DatabaseStrategy(
        database,
        lifetime_seconds=settings.AUTH_SESSION_MAX_AGE_SECONDS,
    )


transport = CookieTransport(
    cookie_name="Authorization",
    cookie_max_age=settings.AUTH_SESSION_MAX_AGE_SECONDS,
    cookie_secure=cookie_secure(),
    cookie_samesite=settings.COOKIE_SAMESITE.lower(),
)


auth_backend = AuthenticationBackend(
    name="database", transport=transport, get_strategy=get_strategy
)
