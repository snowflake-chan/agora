from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyBaseAccessTokenTableUUID
from sqlalchemy import Index

from app.db.base import Base


class AuthSession(SQLAlchemyBaseAccessTokenTableUUID, Base):
    __tablename__ = "auth_session"
    __table_args__ = (Index("ix_auth_session_user_id", "user_id"),)
