import uuid

from fastapi_users.db import (
    SQLAlchemyBaseUserTableUUID
)

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class User(
    SQLAlchemyBaseUserTableUUID,
    Base
):
    pass