"""add immutable content and patch revision history

Revision ID: o4p5q6r7s8t9
Revises: n3o4p5q6r7s8
Create Date: 2026-07-21 21:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "o4p5q6r7s8t9"
down_revision: Union[str, Sequence[str], None] = "n3o4p5q6r7s8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE content ADD COLUMN IF NOT EXISTS revision_number "
        "INTEGER DEFAULT 1"
    )
    op.execute(
        "UPDATE content SET revision_number = 1 WHERE revision_number IS NULL"
    )
    op.execute(
        "ALTER TABLE content ALTER COLUMN revision_number SET DEFAULT 1"
    )
    op.execute(
        "ALTER TABLE content ALTER COLUMN revision_number SET NOT NULL"
    )
    op.execute(
        "ALTER TABLE patch ADD COLUMN IF NOT EXISTS revision_number "
        "INTEGER DEFAULT 1"
    )
    op.execute(
        "UPDATE patch SET revision_number = 1 WHERE revision_number IS NULL"
    )
    op.execute(
        "ALTER TABLE patch ALTER COLUMN revision_number SET DEFAULT 1"
    )
    op.execute("ALTER TABLE patch ALTER COLUMN revision_number SET NOT NULL")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS content_revision (
            id UUID PRIMARY KEY,
            content_id UUID NOT NULL
                REFERENCES content(id) ON DELETE CASCADE,
            version INTEGER NOT NULL,
            title VARCHAR(200),
            content TEXT NOT NULL,
            tags VARCHAR(50)[],
            editor_id UUID NOT NULL
                REFERENCES "user"(id) ON DELETE CASCADE,
            was_public BOOLEAN NOT NULL,
            edited_at TIMESTAMP WITH TIME ZONE NOT NULL
                DEFAULT clock_timestamp(),
            CONSTRAINT uq_content_revision_version
                UNIQUE (content_id, version),
            CONSTRAINT ck_content_revision_version_positive
                CHECK (version > 0)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_content_revision_content_id "
        "ON content_revision (content_id)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS patch_revision (
            id UUID PRIMARY KEY,
            patch_id UUID NOT NULL
                REFERENCES patch(id) ON DELETE CASCADE,
            version INTEGER NOT NULL,
            title VARCHAR(200) NOT NULL,
            content TEXT NOT NULL,
            editor_id UUID NOT NULL
                REFERENCES "user"(id) ON DELETE CASCADE,
            edited_at TIMESTAMP WITH TIME ZONE NOT NULL
                DEFAULT clock_timestamp(),
            CONSTRAINT uq_patch_revision_version
                UNIQUE (patch_id, version),
            CONSTRAINT ck_patch_revision_version_positive
                CHECK (version > 0)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_patch_revision_patch_id "
        "ON patch_revision (patch_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS patch_revision")
    op.execute("DROP TABLE IF EXISTS content_revision")
    op.execute("ALTER TABLE patch DROP COLUMN IF EXISTS revision_number")
    op.execute("ALTER TABLE content DROP COLUMN IF EXISTS revision_number")
