from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)

from app.config import settings


class _LazyAsyncSession:
    """Lazily-initialised async_session so DB URL is only required at runtime."""

    def __init__(self):
        self._maker = None

    def _ensure(self):
        if self._maker is None:
            engine = create_async_engine(settings.DATABASE_URL, echo=True)
            self._maker = async_sessionmaker(engine, expire_on_commit=False)
        return self._maker

    def __call__(self):
        return self._ensure()()


# Public API — drop-in replacement for async_sessionmaker
async_session = _LazyAsyncSession()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
