"""snapshot proposal voting windows

Revision ID: k0l1m2n3o4p5
Revises: j9k0l1m2n3o4
Create Date: 2026-07-20 23:30:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "k0l1m2n3o4p5"
down_revision: Union[str, Sequence[str], None] = "j9k0l1m2n3o4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add retry-safe voting metadata and backfill existing deadlines."""
    op.execute(
        "ALTER TABLE patch ADD COLUMN IF NOT EXISTS voting_started_at "
        "TIMESTAMP WITH TIME ZONE"
    )
    op.execute(
        "ALTER TABLE patch ADD COLUMN IF NOT EXISTS voting_period_hours SMALLINT"
    )
    op.execute(
        "ALTER TABLE patch ADD COLUMN IF NOT EXISTS voting_window_kind VARCHAR(24)"
    )

    op.execute(
        """
        UPDATE patch
        SET voting_started_at = updated_at,
            voting_ends_at = updated_at + INTERVAL '72 hours',
            voting_period_hours = 72,
            voting_window_kind = 'standard'
        WHERE status = 'voting'
          AND voting_ends_at IS NULL
        """
    )

    op.execute(
        """
        UPDATE patch
        SET voting_started_at = voting_ends_at - INTERVAL '72 hours',
            voting_period_hours = 72,
            voting_window_kind = 'standard'
        WHERE voting_ends_at IS NOT NULL
          AND (
              voting_started_at IS NULL
              OR voting_period_hours IS NULL
              OR voting_window_kind IS NULL
          )
        """
    )

    op.execute(
        "ALTER TABLE patch DROP CONSTRAINT IF EXISTS "
        "ck_patch_voting_window_snapshot"
    )
    op.execute(
        """
        ALTER TABLE patch
        ADD CONSTRAINT ck_patch_voting_window_snapshot
        CHECK (
            (
                status != 'voting'
                AND voting_ends_at IS NULL
                AND voting_started_at IS NULL
                AND voting_period_hours IS NULL
                AND voting_window_kind IS NULL
            )
            OR
            (
                status != 'draft'
                AND
                voting_ends_at IS NOT NULL
                AND voting_started_at IS NOT NULL
                AND voting_period_hours IS NOT NULL
                AND voting_window_kind IS NOT NULL
                AND voting_ends_at = (
                    voting_started_at
                    + voting_period_hours * INTERVAL '1 hour'
                )
                AND (
                    (
                        voting_window_kind = 'standard'
                        AND voting_period_hours = 72
                    )
                    OR
                    (
                        voting_window_kind = 'active_creator'
                        AND voting_period_hours = 24
                    )
                )
            )
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_patch_author_merged_updated_at
        ON patch (author_id, updated_at)
        WHERE status = 'merged'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_patch_author_merged_updated_at")
    op.execute(
        "ALTER TABLE patch DROP CONSTRAINT IF EXISTS "
        "ck_patch_voting_window_snapshot"
    )
    op.execute("ALTER TABLE patch DROP COLUMN IF EXISTS voting_window_kind")
    op.execute("ALTER TABLE patch DROP COLUMN IF EXISTS voting_period_hours")
    op.execute("ALTER TABLE patch DROP COLUMN IF EXISTS voting_started_at")
