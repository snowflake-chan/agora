"""add user.bio

Revision ID: 35cecc0cf8cf
Revises: 5dd542e97033
Create Date: 2026-07-19 13:19:44.270663

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '35cecc0cf8cf'
down_revision: Union[str, Sequence[str], None] = '5dd542e97033'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add bio while remaining compatible with pre-migration deployments."""
    # Older releases created this column in the FastAPI lifespan hook. Those
    # databases are still stamped at the previous Alembic revision, so a plain
    # ADD COLUMN makes the backend fail to start during upgrade.
    op.execute(
        'ALTER TABLE "user" ADD COLUMN IF NOT EXISTS bio VARCHAR(500)'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute('ALTER TABLE "user" DROP COLUMN IF EXISTS bio')
