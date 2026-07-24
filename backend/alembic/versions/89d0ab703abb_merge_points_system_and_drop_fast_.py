"""merge points system and drop fast_tracked heads

Revision ID: 89d0ab703abb
Revises: dr0pf4sttr4ck, n001p01nt5y5t3m
Create Date: 2026-07-24 14:34:07.185117

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '89d0ab703abb'
down_revision: Union[str, Sequence[str], None] = ('dr0pf4sttr4ck', 'n001p01nt5y5t3m')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
