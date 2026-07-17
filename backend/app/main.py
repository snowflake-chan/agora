from fastapi import FastAPI
from app.users import auth_router, users_router
from app.posts import posts_router
from app.patches import patches_router

app = FastAPI()

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users_router, prefix="/api/v1/users", tags=["users"])
app.include_router(posts_router, prefix="/api/v1/posts", tags=["posts"])
app.include_router(patches_router, prefix="/api/v1/patches", tags=["patches"])