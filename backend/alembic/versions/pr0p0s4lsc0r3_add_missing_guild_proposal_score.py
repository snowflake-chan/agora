"""add missing guild.proposal_score column

Revision ID: pr0p0s4lsc0r3
Revises: r3cr34t3t0k3nt4bl3s
Create Date: 2026-07-22 16:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "pr0p0s4lsc0r3"
down_revision: Union[str, Sequence[str], None] = "r3cr34t3t0k3nt4bl3s"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE guild ADD COLUMN IF NOT EXISTS proposal_score INTEGER NOT NULL DEFAULT 0")


def downgrade() -> None:
    op.execute("ALTER TABLE guild DROP COLUMN IF EXISTS proposal_score")
