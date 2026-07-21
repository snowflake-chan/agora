"""add durable moderation publication and delivery state

Revision ID: n3o4p5q6r7s8
Revises: m2n3o4p5q6r7
Create Date: 2026-07-21 18:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "n3o4p5q6r7s8"
down_revision: Union[str, Sequence[str], None] = "m2n3o4p5q6r7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE content ADD COLUMN IF NOT EXISTS published_at "
        "TIMESTAMP WITH TIME ZONE"
    )
    op.execute(
        "ALTER TABLE content ADD COLUMN IF NOT EXISTS "
        "moderation_effects_completed_at TIMESTAMP WITH TIME ZONE"
    )
    op.execute(
        "ALTER TABLE notification ADD COLUMN IF NOT EXISTS dedupe_key VARCHAR(200)"
    )
    op.execute(
        "UPDATE content SET published_at = "
        "COALESCE(moderation_reviewed_at, created_at) "
        "WHERE moderation_status = 'approved' AND published_at IS NULL"
    )
    # Rows reviewed before this outbox existed already ran the legacy inline
    # side effects. Mark them complete so the first reconciler pass cannot
    # duplicate historical notifications.
    op.execute(
        "UPDATE content SET moderation_effects_completed_at = "
        "COALESCE(moderation_reviewed_at, created_at) "
        "WHERE moderation_status IN ('approved', 'rejected') "
        "AND moderation_effects_completed_at IS NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_notification_dedupe_key "
        "ON notification (dedupe_key)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_notification_dedupe_key")
    op.execute("ALTER TABLE notification DROP COLUMN IF EXISTS dedupe_key")
    op.execute(
        "ALTER TABLE content DROP COLUMN IF EXISTS "
        "moderation_effects_completed_at"
    )
    op.execute("ALTER TABLE content DROP COLUMN IF EXISTS published_at")
