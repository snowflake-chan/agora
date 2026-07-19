from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.users import auth_router, users_router
from app.posts import posts_router
from app.patches import patches_router
from app.notifications import router as notifications_router

app = FastAPI()

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
app.include_router(notifications_router, prefix="/api/v1/notifications", tags=["notifications"])
