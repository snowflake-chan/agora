"""merge multiple heads: add_user_bio + guilds chain + stub

Revision ID: m001m3rg3h34ds
Revises: 35cecc0cf8cf, 8f5c7f0ee676, g6h7i8j9k0l1
Create Date: 2026-07-19 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'm001m3rg3h34ds'
down_revision: Union[str, Sequence[str], None] = ('35cecc0cf8cf', '8f5c7f0ee676', 'g6h7i8j9k0l1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
