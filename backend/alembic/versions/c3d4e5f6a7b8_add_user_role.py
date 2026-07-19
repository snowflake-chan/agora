"""add user role

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-19 23:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user', sa.Column('role', sa.String(length=20), nullable=True, server_default='user'))
    op.execute(sa.text("UPDATE \"user\" SET role = 'user' WHERE role IS NULL"))


def downgrade() -> None:
    op.drop_column('user', 'role')
