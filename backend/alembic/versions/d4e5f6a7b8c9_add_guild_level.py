"""add guild level

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-19 23:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('guild', sa.Column('level', sa.Integer(), nullable=True, server_default='1'))
    op.execute(sa.text("UPDATE guild SET level = 1 WHERE level IS NULL"))
    op.alter_column('guild', 'level', nullable=False)


def downgrade() -> None:
    op.drop_column('guild', 'level')
