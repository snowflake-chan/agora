"""add missing user.created_at column

Revision ID: us3r4cr34t3d4t
Revises: pr0p0s4lsc0r3
Create Date: 2026-07-22 16:10:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "us3r4cr34t3d4t"
down_revision: Union[str, Sequence[str], None] = "pr0p0s4lsc0r3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()")


def downgrade() -> None:
    op.execute("ALTER TABLE \"user\" DROP COLUMN IF EXISTS created_at")
