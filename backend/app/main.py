import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.moderation_delivery import (
    reconcile_moderation_effects,
    run_moderation_delivery_scheduler,
)
from app.patches.reconcile import reconcile as reconcile_patches
from app.patches.reconcile import run_scheduler
from app.users import auth_router, users_router
from app.posts import posts_router
from app.patches import patches_router
from app.guilds import router as guilds_router
from app.admin import router as admin_router
from app.notifications import router as notifications_router
from app.public import router as public_router
from app.ai.routes import router as ai_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Recover durable jobs, then keep them independent of request traffic."""
    await reconcile_patches()
    await reconcile_moderation_effects()
    schedulers = (
        asyncio.create_task(run_scheduler()),
        asyncio.create_task(
            run_moderation_delivery_scheduler(
                settings.GOVERNANCE_POLL_SECONDS
            )
        ),
    )
    try:
        yield
    finally:
        for scheduler in schedulers:
            scheduler.cancel()
        for scheduler in schedulers:
            with suppress(asyncio.CancelledError):
                await scheduler


app = FastAPI(lifespan=lifespan)

# CORS — allow frontend origin
if settings.CORS_ORIGIN:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.CORS_ORIGIN],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users_router, prefix="/api/v1/users", tags=["users"])
app.include_router(posts_router, prefix="/api/v1/posts", tags=["posts"])
app.include_router(patches_router, prefix="/api/v1/patches", tags=["patches"])
app.include_router(guilds_router, prefix="/api/v1/guilds", tags=["guilds"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(notifications_router, prefix="/api/v1/notifications", tags=["notifications"])
app.include_router(public_router, prefix="/api/v1/public", tags=["public"])
app.include_router(ai_router, prefix="/api/v1/ai", tags=["ai"])
