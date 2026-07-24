"""Merge st4k3qu3stf1n3 and us3r4cr34t3d4t

Revision ID: d7becddb4a4d
Revises: st4k3qu3stf1n3, us3r4cr34t3d4t
Create Date: 2026-07-23 00:18:04.834734

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7becddb4a4d'
down_revision: Union[str, Sequence[str], None] = ('st4k3qu3stf1n3', 'us3r4cr34t3d4t')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
