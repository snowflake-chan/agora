"""Dependencies for the users module.

Stands alone so auth.py and users.py don't circular-import current_user.
"""
from fastapi_users import FastAPIUsers
from .manager import get_user_manager
from .backend import auth_backend

fastapi_users = FastAPIUsers(get_user_manager, [auth_backend])
current_user = fastapi_users.current_user()
optional_current_user = fastapi_users.current_user(optional=True)
