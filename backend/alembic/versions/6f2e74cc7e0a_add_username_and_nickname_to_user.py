"""add username and nickname to user

Revision ID: 6f2e74cc7e0a
Revises: 11d03af40276
Create Date: 2026-07-17 15:28:43.032913

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f2e74cc7e0a'
down_revision: Union[str, Sequence[str], None] = '11d03af40276'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Add as nullable first
    op.add_column('user', sa.Column('username', sa.String(length=50), nullable=True))
    op.add_column('user', sa.Column('nickname', sa.String(length=100), nullable=True))

    # 2. Backfill existing rows with a unique username from their email
    op.execute(
        "UPDATE \"user\" SET username = split_part(email, '@', 1) || '-' || substr(md5(id::text)::text, 1, 6) WHERE username IS NULL"
    )

    # 3. Now make it NOT NULL and unique
    op.alter_column('user', 'username', nullable=False)
    op.create_unique_constraint('uq_user_username', 'user', ['username'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_user_username', 'user', type_='unique')
    op.drop_column('user', 'nickname')
    op.drop_column('user', 'username')
