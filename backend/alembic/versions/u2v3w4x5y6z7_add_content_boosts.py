"""add content boosts

Revision ID: b00st3u2v3w4x5y6
Revises: t0k3n1m2n3o4p5
Create Date: 2026-07-21 16:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP


revision: str = "b00st3u2v3w4x5y6"
down_revision: Union[str, Sequence[str], None] = "t0k3n1m2n3o4p5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS content_boosts (
            id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
            content_id UUID NOT NULL REFERENCES content(id) ON DELETE CASCADE,
            tier TEXT NOT NULL,
            weight DOUBLE PRECISION NOT NULL,
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_content_boost_content_id ON content_boosts (content_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_content_boost_expires ON content_boosts (expires_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS content_boosts")
