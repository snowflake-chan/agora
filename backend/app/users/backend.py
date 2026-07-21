from fastapi_users.authentication import AuthenticationBackend
from fastapi_users.authentication import CookieTransport
from fastapi_users.authentication import JWTStrategy
from app.config import settings


def get_strategy():
    return JWTStrategy(
        secret=settings.JWT_SECRET,
        lifetime_seconds=3600,
    )


transport = CookieTransport(
    cookie_name="Authorization",
    cookie_max_age=3600,
    cookie_secure=settings.COOKIE_SECURE,
    cookie_samesite=settings.COOKIE_SAMESITE.lower(),
)


auth_backend = AuthenticationBackend(
    name="jwt", transport=transport, get_strategy=get_strategy
)
