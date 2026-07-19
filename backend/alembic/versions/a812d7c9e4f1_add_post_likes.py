"""add post likes

Revision ID: a812d7c9e4f1
Revises: 35cecc0cf8cf
Create Date: 2026-07-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a812d7c9e4f1"
down_revision: Union[str, Sequence[str], None] = "35cecc0cf8cf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "post_like",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["content.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("post_id", "user_id", name="uq_post_like_post_user"),
    )
    op.create_index("ix_post_like_post_id", "post_like", ["post_id"])
    op.create_index("ix_post_like_user_id", "post_like", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_post_like_user_id", table_name="post_like")
    op.drop_index("ix_post_like_post_id", table_name="post_like")
    op.drop_table("post_like")
