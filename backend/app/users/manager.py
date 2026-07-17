import uuid

from fastapi_users import BaseUserManager, exceptions
from app.config import settings
from fastapi import Depends
from app.db.models.user import get_user_db

class UserManager(BaseUserManager):
    reset_password_token_secret = settings.JWT_SECRET
    verification_token_secret = settings.JWT_SECRET

    def parse_id(self, value: str) -> uuid.UUID:
        try:
            return uuid.UUID(value)
        except ValueError:
            raise exceptions.InvalidID()
    
async def get_user_manager(
    user_db=Depends(get_user_db)
):
    yield UserManager(user_db)