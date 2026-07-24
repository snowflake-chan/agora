"""add missing columns to token_balances

Revision ID: m1ss1ngc0lumns
Revises: b27ee7b3c853
Create Date: 2026-07-22 15:15:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "m1ss1ngc0lumns"
down_revision: Union[str, Sequence[str], None] = "b27ee7b3c853"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE token_balances ADD COLUMN IF NOT EXISTS total_earned INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE token_balances ADD COLUMN IF NOT EXISTS total_spent INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE token_balances ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()")
    op.execute("ALTER TABLE token_balances ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()")


def downgrade() -> None:
    op.execute("ALTER TABLE token_balances DROP COLUMN IF EXISTS total_earned")
    op.execute("ALTER TABLE token_balances DROP COLUMN IF EXISTS total_spent")
    op.execute("ALTER TABLE token_balances DROP COLUMN IF EXISTS created_at")
    op.execute("ALTER TABLE token_balances DROP COLUMN IF EXISTS updated_at")
