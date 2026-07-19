"""add bio to user

Revision ID: 3a8f5b1c9d2e
Revises: 5dd542e97033
Create Date: 2026-07-19 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a8f5b1c9d2e'
down_revision: Union[str, Sequence[str], None] = '5dd542e97033'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add a nullable `bio` column to the user table.

    Idempotent: skip if the column already exists (e.g. from manual ALTER
    statements that ran before this migration was created).
    """
    conn = op.get_bind()
    exists = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'user' AND column_name = 'bio'"
    )).first()
    if not exists:
        op.add_column('user', sa.Column('bio', sa.String(length=500), nullable=True))


def downgrade() -> None:
    """Remove the `bio` column from the user table."""
    op.drop_column('user', 'bio')
