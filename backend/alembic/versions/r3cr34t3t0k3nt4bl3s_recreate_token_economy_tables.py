"""recreate token economy tables to match ORM models exactly

All tables are empty, so we drop and recreate them cleanly.
Merge rev: m1ss1ngc0lumns

Revision ID: r3cr34t3t0k3nt4bl3s
Revises: m1ss1ngc0lumns
Create Date: 2026-07-22 15:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "r3cr34t3t0k3nt4bl3s"
down_revision: Union[str, Sequence[str], None] = "m1ss1ngc0lumns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop all token-related tables (order matters for FKs)
    op.execute("DROP TABLE IF EXISTS guild_member_proposals CASCADE")
    op.execute("DROP TABLE IF EXISTS token_snapshots CASCADE")
    op.execute("DROP TABLE IF EXISTS token_params_history CASCADE")
    op.execute("DROP TABLE IF EXISTS token_params CASCADE")
    op.execute("DROP TABLE IF EXISTS token_transactions CASCADE")
    op.execute("DROP TABLE IF EXISTS token_balances CASCADE")

    # Recreate token_balances
    op.create_table(
        "token_balances",
        sa.Column("user_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("balance", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_earned", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_spent", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Recreate token_transactions
    op.create_table(
        "token_transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("reference_id", UUID(as_uuid=True), nullable=True),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Recreate token_params
    op.create_table(
        "token_params",
        sa.Column("key", sa.String(50), primary_key=True),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("updated_by", UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Recreate token_params_history
    op.create_table(
        "token_params_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("key", sa.String(50), nullable=False),
        sa.Column("old_value", sa.Integer(), nullable=False),
        sa.Column("new_value", sa.Integer(), nullable=False),
        sa.Column("changed_by", UUID(as_uuid=True), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Recreate token_snapshots
    op.create_table(
        "token_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("snapshot_date", sa.Date(), nullable=False, unique=True, index=True),
        sa.Column("circulating_supply", sa.Integer(), nullable=False),
        sa.Column("total_issued", sa.Integer(), nullable=False),
        sa.Column("total_burned", sa.Integer(), nullable=False),
        sa.Column("active_users", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("transaction_count_24h", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Recreate guild_member_proposals
    op.create_table(
        "guild_member_proposals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("guild_id", UUID(as_uuid=True), sa.ForeignKey("guild.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("proposal_id", UUID(as_uuid=True), sa.ForeignKey("patch.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("counted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Insert default token params
    defaults = [
        ("daily_issuance", 5000),
        ("like_reward", 2),
        ("vote_reward", 2),
        ("proposal_pass_reward", 100),
        ("daily_login_base", 3),
        ("proposal_deposit", 50),
        ("boost_price_low", 10),
        ("boost_price_mid", 30),
        ("boost_price_high", 50),
        ("guild_create_fee", 200),
        ("daily_user_cap", 200),
    ]
    for key, val in defaults:
        op.execute(
            f"INSERT INTO token_params (key, value) VALUES ('{key}', {val}) ON CONFLICT (key) DO NOTHING"
        )


def downgrade() -> None:
    pass
