"""add token economy and guild proposal leveling

Revision ID: t0k3n1m2n3o4p5
Revises: k0l1m2n3o4p5
Create Date: 2026-07-21 15:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP


revision: str = "t0k3n1m2n3o4p5"
down_revision: Union[str, Sequence[str], None] = "k0l1m2n3o4p5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # token_balances
    op.execute("""
        CREATE TABLE IF NOT EXISTS token_balances (
            user_id UUID NOT NULL PRIMARY KEY REFERENCES "user"(id) ON DELETE CASCADE,
            balance BIGINT NOT NULL DEFAULT 0 CHECK (balance >= 0)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS token_transactions (
            id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            delta BIGINT NOT NULL,
            balance_after BIGINT NOT NULL CHECK (balance_after >= 0),
            source TEXT NOT NULL,
            reference_id TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_token_txn_user_id ON token_transactions (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_token_txn_created_at ON token_transactions (created_at DESC)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS token_params (
            key TEXT NOT NULL PRIMARY KEY,
            value BIGINT NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS token_params_history (
            id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
            key TEXT NOT NULL,
            old_value BIGINT NOT NULL,
            new_value BIGINT NOT NULL,
            changed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            changed_by UUID REFERENCES "user"(id)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS guild_member_proposals (
            id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
            guild_id UUID NOT NULL REFERENCES guild(id) ON DELETE CASCADE,
            patch_id UUID NOT NULL REFERENCES patch(id) ON DELETE CASCADE,
            author_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            CONSTRAINT uq_guild_member_proposal_patch UNIQUE (patch_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_gmp_guild_id ON guild_member_proposals (guild_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_gmp_author_id ON guild_member_proposals (author_id)")

    # Guild level column
    op.execute("ALTER TABLE guild ADD COLUMN IF NOT EXISTS level INTEGER NOT NULL DEFAULT 1 CHECK (level BETWEEN 1 AND 5)")

    # Default token params
    defaults = [
        ("daily_issuance", "1000"),
        ("like_reward", "1"),
        ("vote_reward", "5"),
        ("proposal_pass_reward", "30"),
        ("daily_login_base", "5"),
        ("proposal_deposit", "50"),
        ("boost_price_low", "10"),
        ("boost_price_mid", "25"),
        ("boost_price_high", "50"),
        ("guild_create_fee", "100"),
        ("daily_user_cap", "100"),
    ]
    for key, val in defaults:
        op.execute(f"INSERT INTO token_params (key, value) VALUES ('{key}', {val}) ON CONFLICT (key) DO NOTHING")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS guild_member_proposals")
    op.execute("ALTER TABLE guild DROP COLUMN IF EXISTS level")
    op.execute("DROP TABLE IF EXISTS token_params_history")
    op.execute("DROP TABLE IF EXISTS token_params")
    op.execute("DROP TABLE IF EXISTS token_transactions")
    op.execute("DROP TABLE IF EXISTS token_balances")
