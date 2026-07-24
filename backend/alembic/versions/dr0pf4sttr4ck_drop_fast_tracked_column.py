"""Drop fast_tracked column and restore voting window snapshot

Revision ID: dr0pf4sttr4ck
Revises: d7becddb4a4d
Create Date: 2026-07-24

- Remove the unused fast_tracked column that was added by the now-deleted
  f4s7tr4ck migration. The fast-track voting feature has been removed in
  favor of the unified admin "shorten voting" action.
- Restore the ck_patch_voting_window_snapshot check constraint that the
  deleted f4s7tr4ck migration had dropped.
- Clear invalid leftover voting metadata on draft patches before restoring
  the constraint (the previous migration dropped the constraint, which
  allowed inconsistent rows to accumulate during testing).
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "dr0pf4sttr4ck"
down_revision: Union[str, Sequence[str], None] = "d7becddb4a4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("patch", "fast_tracked")

    # Clear stray voting metadata on non-voting patches so the restored
    # check constraint can validate cleanly. Only patches in 'voting' or
    # terminal states are expected to carry voting metadata; drafts must
    # have all four columns NULL.
    op.execute(
        """
        UPDATE patch
        SET voting_started_at = NULL,
            voting_ends_at = NULL,
            voting_period_hours = NULL,
            voting_window_kind = NULL
        WHERE status = 'draft'
          AND (
              voting_started_at IS NOT NULL
              OR voting_ends_at IS NOT NULL
              OR voting_period_hours IS NOT NULL
              OR voting_window_kind IS NOT NULL
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


def downgrade() -> None:
    op.execute(
        "ALTER TABLE patch DROP CONSTRAINT IF EXISTS "
        "ck_patch_voting_window_snapshot"
    )
    op.add_column(
        "patch",
        sa.Column(
            "fast_tracked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
