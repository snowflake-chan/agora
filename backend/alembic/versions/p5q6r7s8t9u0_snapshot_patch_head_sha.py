"""snapshot the governed pull-request head commit

Revision ID: p5q6r7s8t9u0
Revises: o4p5q6r7s8t9
Create Date: 2026-07-21 22:15:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "p5q6r7s8t9u0"
down_revision: Union[str, Sequence[str], None] = "o4p5q6r7s8t9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE patch ADD COLUMN IF NOT EXISTS submitted_head_sha VARCHAR(64)"
    )
    op.execute(
        "UPDATE content SET published_at = "
        "COALESCE(moderation_reviewed_at, created_at) "
        "WHERE moderation_status IN ('published', 'approved') "
        "AND published_at IS NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE patch DROP COLUMN IF EXISTS submitted_head_sha")
