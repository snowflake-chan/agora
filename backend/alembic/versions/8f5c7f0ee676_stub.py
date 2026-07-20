"""stub – previously deleted revision

Revision ID: 8f5c7f0ee676
Revises: 5dd542e97033
Create Date: 2026-07-19 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '8f5c7f0ee676'
down_revision: Union[str, Sequence[str], None] = '5dd542e97033'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
