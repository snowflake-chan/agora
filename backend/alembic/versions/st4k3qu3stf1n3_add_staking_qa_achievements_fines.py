"""add staking, paid Q&A, achievements, violation fines, and weighted voting

Revision ID: st4k3qu3stf1n3
Revises: b27ee7b3c853
Create Date: 2026-07-22 17:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP


revision: str = "st4k3qu3stf1n3"
down_revision: Union[str, Sequence[str], None] = "b27ee7b3c853"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Token staking ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS token_stakes (
            id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            amount BIGINT NOT NULL CHECK (amount > 0),
            pool_type VARCHAR(20) NOT NULL,
            reference_id UUID,
            locked_until TIMESTAMP WITH TIME ZONE,
            apy DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            pending_yield BIGINT NOT NULL DEFAULT 0,
            last_compound_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            is_active BOOLEAN NOT NULL DEFAULT TRUE
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_token_stakes_user_id ON token_stakes (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_token_stakes_pool_type ON token_stakes (pool_type)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS token_yield_records (
            id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
            stake_id UUID NOT NULL REFERENCES token_stakes(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            amount BIGINT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_token_yield_records_stake_id ON token_yield_records (stake_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_token_yield_records_user_id ON token_yield_records (user_id)")

    # ── User achievements ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_achievements (
            id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            achievement_key VARCHAR(50) NOT NULL,
            tier INTEGER NOT NULL CHECK (tier BETWEEN 1 AND 4),
            score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            awarded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_achievements_user_id ON user_achievements (user_id)")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_user_achievement_key "
        "ON user_achievements (user_id, achievement_key)"
    )

    # ── Paid Q&A ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS paid_questions (
            id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
            from_user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            to_user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            question_text TEXT NOT NULL,
            amount BIGINT NOT NULL CHECK (amount > 0),
            is_anonymous BOOLEAN NOT NULL DEFAULT FALSE,
            is_answered BOOLEAN NOT NULL DEFAULT FALSE,
            answer_text TEXT,
            is_paid BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            answered_at TIMESTAMP WITH TIME ZONE
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_paid_questions_from_user ON paid_questions (from_user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_paid_questions_to_user ON paid_questions (to_user_id)")

    # ── Violation fines ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS violation_fines (
            id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            amount BIGINT NOT NULL CHECK (amount > 0),
            reason TEXT NOT NULL,
            reference_type VARCHAR(20) NOT NULL,
            reference_id UUID,
            issued_by UUID REFERENCES "user"(id) ON DELETE SET NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            issued_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            paid_at TIMESTAMP WITH TIME ZONE
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_violation_fines_user_id ON violation_fines (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_violation_fines_status ON violation_fines (status)")

    # ── Weighted voting columns on vote table ──
    op.execute("ALTER TABLE vote ADD COLUMN IF NOT EXISTS stake_amount BIGINT NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE vote ADD COLUMN IF NOT EXISTS weight DOUBLE PRECISION NOT NULL DEFAULT 1.0")


def downgrade() -> None:
    op.execute("ALTER TABLE vote DROP COLUMN IF EXISTS weight")
    op.execute("ALTER TABLE vote DROP COLUMN IF EXISTS stake_amount")
    op.execute("DROP TABLE IF EXISTS violation_fines")
    op.execute("DROP TABLE IF EXISTS paid_questions")
    op.execute("DROP TABLE IF EXISTS user_achievements")
    op.execute("DROP TABLE IF EXISTS token_yield_records")
    op.execute("DROP TABLE IF EXISTS token_stakes")