"""add points system: user.points, user.first_guild_id, guild.points, point_transaction table

Revision ID: n001p01nt5y5t3m
Revises: m001m3rg3h34ds
Create Date: 2026-07-20 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'n001p01nt5y5t3m'
down_revision: Union[str, Sequence[str], None] = 'm001m3rg3h34ds'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add points to user
    op.add_column("user", sa.Column("points", sa.Integer(), nullable=False, server_default="0"))
    # Add first_guild_id to user
    op.add_column("user", sa.Column("first_guild_id", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_user_first_guild", "user", "guild", ["first_guild_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_user_first_guild_id", "user", ["first_guild_id"])

    # Add points to guild
    op.add_column("guild", sa.Column("points", sa.Integer(), nullable=False, server_default="0"))

    # Create point_transaction table
    op.create_table(
        "point_transaction",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("guild_id", sa.UUID(), nullable=True),
        sa.Column("patch_id", sa.UUID(), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(50), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_point_transaction_user_id", "point_transaction", ["user_id"])
    op.create_index("ix_point_transaction_guild_id", "point_transaction", ["guild_id"])
    op.create_index("ix_point_transaction_patch_id", "point_transaction", ["patch_id"])
    op.create_foreign_key("fk_point_transaction_user", "point_transaction", "user", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_point_transaction_guild", "point_transaction", "guild", ["guild_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_point_transaction_patch", "point_transaction", "patch", ["patch_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_table("point_transaction")
    op.drop_column("guild", "points")
    op.drop_constraint("fk_user_first_guild", "user", type_="foreignkey")
    op.drop_index("ix_user_first_guild_id", table_name="user")
    op.drop_column("user", "first_guild_id")
    op.drop_column("user", "points")