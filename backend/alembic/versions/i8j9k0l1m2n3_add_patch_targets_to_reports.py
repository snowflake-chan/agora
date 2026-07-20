"""add patch targets to reports

Revision ID: i8j9k0l1m2n3
Revises: h7i8j9k0l1m2
Create Date: 2026-07-20 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "i8j9k0l1m2n3"
down_revision: Union[str, Sequence[str], None] = "h7i8j9k0l1m2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add a retry-safe optional patch target to existing reports."""
    op.execute("ALTER TABLE report ADD COLUMN IF NOT EXISTS patch_id UUID")
    op.execute(
        """
        DO $$
        DECLARE existing_fk RECORD;
        BEGIN
            FOR existing_fk IN (
                SELECT conname
                FROM pg_constraint
                WHERE conrelid = 'report'::regclass
                  AND contype = 'f'
                  AND conkey @> ARRAY[(
                      SELECT attnum
                      FROM pg_attribute
                      WHERE attrelid = 'report'::regclass
                        AND attname = 'patch_id'
                  )]
            ) LOOP
                EXECUTE format(
                    'ALTER TABLE report DROP CONSTRAINT %I',
                    existing_fk.conname
                );
            END LOOP;

            ALTER TABLE report
            ADD CONSTRAINT report_patch_id_fkey
            FOREIGN KEY (patch_id) REFERENCES patch(id) ON DELETE SET NULL;

            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conrelid = 'report'::regclass
                  AND conname = 'ck_report_single_target'
            ) THEN
                ALTER TABLE report
                ADD CONSTRAINT ck_report_single_target
                CHECK (content_id IS NULL OR patch_id IS NULL);
            END IF;
        END $$;
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_report_patch_id ON report (patch_id)"
    )


def downgrade() -> None:
    """Remove patch report targets without touching content reports."""
    op.execute("DROP INDEX IF EXISTS ix_report_patch_id")
    op.execute(
        "ALTER TABLE report DROP CONSTRAINT IF EXISTS ck_report_single_target"
    )
    op.execute(
        "ALTER TABLE report DROP CONSTRAINT IF EXISTS report_patch_id_fkey"
    )
    op.execute("ALTER TABLE report DROP COLUMN IF EXISTS patch_id")
