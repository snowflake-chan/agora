"""add token snapshots

Revision ID: sn4ps3v3w4x5y6z7
Revises: b00st3u2v3w4x5y6
Create Date: 2026-07-21 23:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP


revision: str = "sn4ps3v3w4x5y6z7"
down_revision: Union[str, Sequence[str], None] = "b00st3u2v3w4x5y6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS token_snapshots (
            id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
            circulating_supply BIGINT NOT NULL,
            total_issued BIGINT NOT NULL,
            total_burned BIGINT NOT NULL,
            snapshot_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_token_snapshots_at ON token_snapshots (snapshot_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS token_snapshots")
