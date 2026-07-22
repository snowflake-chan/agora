"""add revocable authentication sessions

Revision ID: q6r7s8t9u0v1
Revises: p5q6r7s8t9u0
Create Date: 2026-07-21 23:55:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "q6r7s8t9u0v1"
down_revision: Union[str, Sequence[str], None] = "p5q6r7s8t9u0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        '''
        CREATE TABLE IF NOT EXISTS auth_session (
            token VARCHAR(43) PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            user_id UUID NOT NULL REFERENCES "user" (id) ON DELETE CASCADE
        )
        '''
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_auth_session_created_at "
        "ON auth_session (created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_auth_session_user_id "
        "ON auth_session (user_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_auth_session_user_id")
    op.execute("DROP INDEX IF EXISTS ix_auth_session_created_at")
    op.execute("DROP TABLE IF EXISTS auth_session")
