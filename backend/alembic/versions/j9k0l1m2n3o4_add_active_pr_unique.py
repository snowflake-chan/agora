"""enforce one active proposal per pull request

Revision ID: j9k0l1m2n3o4
Revises: i8j9k0l1m2n3
Create Date: 2026-07-20 22:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "j9k0l1m2n3o4"
down_revision: Union[str, Sequence[str], None] = "i8j9k0l1m2n3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add a retry-safe partial unique index after checking old duplicates."""
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM patch
                WHERE status IN ('draft', 'voting', 'passed')
                GROUP BY pr_number
                HAVING COUNT(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'Cannot add active PR uniqueness: duplicate active pr_number values exist';
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_patch_active_pr_number
        ON patch (pr_number)
        WHERE status IN ('draft', 'voting', 'passed')
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_patch_active_pr_number")
