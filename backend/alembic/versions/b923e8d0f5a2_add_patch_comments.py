"""add patch comments

Revision ID: b923e8d0f5a2
Revises: a812d7c9e4f1
Create Date: 2026-07-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b923e8d0f5a2"
down_revision: Union[str, Sequence[str], None] = "a812d7c9e4f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "content",
        sa.Column("patch_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_content_patch_id_patch",
        "content",
        "patch",
        ["patch_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_content_patch_id", "content", ["patch_id"])


def downgrade() -> None:
    op.drop_index("ix_content_patch_id", table_name="content")
    op.drop_constraint("fk_content_patch_id_patch", "content", type_="foreignkey")
    op.drop_column("content", "patch_id")
