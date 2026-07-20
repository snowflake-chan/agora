"""add follows

Revision ID: c034f9e1a6b3
Revises: b923e8d0f5a2
Create Date: 2026-07-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c034f9e1a6b3"
down_revision: Union[str, Sequence[str], None] = "b923e8d0f5a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "follow",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("follower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("following_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["follower_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["following_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("follower_id", "following_id", name="uq_follow_pair"),
    )
    op.create_index("ix_follow_follower_id", "follow", ["follower_id"])
    op.create_index("ix_follow_following_id", "follow", ["following_id"])


def downgrade() -> None:
    op.drop_index("ix_follow_following_id", table_name="follow")
    op.drop_index("ix_follow_follower_id", table_name="follow")
    op.drop_table("follow")
