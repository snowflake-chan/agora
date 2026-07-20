from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)

from app.config import settings


class _LazyAsyncSession:
    """Lazily-initialised async_session so DB URL is only required at runtime.

    create_async_engine() is synchronous (defers connect to first query),
    so init is safe to call from any context without awaiting.
    """

    def __init__(self):
        self._maker = None

    def _ensure(self):
        """Sync init — create_async_engine() does NOT require await."""
        if self._maker is None:
            # SQL logging can expose report text, emails, and other user data.
            # Keep it opt-in for local debugging rather than enabled in production.
            engine = create_async_engine(settings.DATABASE_URL, echo=settings.DB_ECHO)
            self._maker = async_sessionmaker(engine, expire_on_commit=False)

    def __call__(self):
        self._ensure()
        return self._maker()


# Public API — drop-in replacement for async_sessionmaker
async_session = _LazyAsyncSession()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
