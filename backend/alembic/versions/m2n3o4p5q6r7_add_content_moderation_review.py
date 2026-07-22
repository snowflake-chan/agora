"""add automated content moderation review state

Revision ID: m2n3o4p5q6r7
Revises: l1m2n3o4p5q6
Create Date: 2026-07-21 12:30:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "m2n3o4p5q6r7"
down_revision: Union[str, Sequence[str], None] = "l1m2n3o4p5q6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE content ADD COLUMN IF NOT EXISTS moderation_status "
        "VARCHAR(24) DEFAULT 'published'"
    )
    op.execute(
        "ALTER TABLE content ADD COLUMN IF NOT EXISTS moderation_reason VARCHAR(64)"
    )
    op.execute(
        "ALTER TABLE content ADD COLUMN IF NOT EXISTS moderation_review_note TEXT"
    )
    op.execute(
        "ALTER TABLE content ADD COLUMN IF NOT EXISTS moderation_reviewed_by UUID"
    )
    op.execute(
        "ALTER TABLE content ADD COLUMN IF NOT EXISTS moderation_reviewed_at "
        "TIMESTAMP WITH TIME ZONE"
    )
    op.execute(
        "UPDATE content SET moderation_status = 'published' "
        "WHERE moderation_status IS NULL"
    )
    op.execute(
        "ALTER TABLE content ALTER COLUMN moderation_status SET DEFAULT 'published'"
    )
    op.execute(
        "ALTER TABLE content ALTER COLUMN moderation_status SET NOT NULL"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_content_moderation_status'
                  AND conrelid = 'content'::regclass
            ) THEN
                ALTER TABLE content
                ADD CONSTRAINT ck_content_moderation_status
                CHECK (
                    moderation_status IN (
                        'published', 'pending_review', 'approved', 'rejected'
                    )
                );
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'content_moderation_reviewed_by_fkey'
                  AND conrelid = 'content'::regclass
            ) THEN
                ALTER TABLE content
                ADD CONSTRAINT content_moderation_reviewed_by_fkey
                FOREIGN KEY (moderation_reviewed_by)
                REFERENCES "user"(id) ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_content_moderation_status "
        "ON content (moderation_status)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_content_moderation_status")
    op.execute(
        "ALTER TABLE content DROP CONSTRAINT IF EXISTS "
        "content_moderation_reviewed_by_fkey"
    )
    op.execute(
        "ALTER TABLE content DROP CONSTRAINT IF EXISTS ck_content_moderation_status"
    )
    op.execute(
        "ALTER TABLE content DROP COLUMN IF EXISTS moderation_reviewed_at"
    )
    op.execute(
        "ALTER TABLE content DROP COLUMN IF EXISTS moderation_reviewed_by"
    )
    op.execute(
        "ALTER TABLE content DROP COLUMN IF EXISTS moderation_review_note"
    )
    op.execute("ALTER TABLE content DROP COLUMN IF EXISTS moderation_reason")
    op.execute("ALTER TABLE content DROP COLUMN IF EXISTS moderation_status")
