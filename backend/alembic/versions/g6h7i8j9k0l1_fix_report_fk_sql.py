"""fix report FK to SET NULL (raw SQL for safety)

Revision ID: g6h7i8j9k0l1
Revises: f6a7b8c9d0e1
Create Date: 2026-07-20 01:00:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = 'g6h7i8j9k0l1'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop any existing FK on report.content_id (regardless of name)
    op.execute("""
        DO $$
        DECLARE r RECORD;
        BEGIN
            FOR r IN (SELECT conname FROM pg_constraint
                       WHERE conrelid = 'report'::regclass AND contype = 'f'
                         AND conkey @> ARRAY[(SELECT attnum FROM pg_attribute
                           WHERE attrelid = 'report'::regclass AND attname = 'content_id')])
            LOOP
                EXECUTE 'ALTER TABLE report DROP CONSTRAINT ' || r.conname;
            END LOOP;
        END $$;
    """)
    # Re-create with SET NULL
    op.execute("ALTER TABLE report ADD CONSTRAINT report_content_id_fkey FOREIGN KEY (content_id) REFERENCES content(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE report ALTER COLUMN content_id DROP NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE report DROP CONSTRAINT IF EXISTS report_content_id_fkey")
    op.execute("ALTER TABLE report ADD CONSTRAINT report_content_id_fkey FOREIGN KEY (content_id) REFERENCES content(id) ON DELETE CASCADE")
