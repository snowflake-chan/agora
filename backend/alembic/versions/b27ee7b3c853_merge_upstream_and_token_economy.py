"""merge upstream and token economy

Revision ID: b27ee7b3c853
Revises: q6r7s8t9u0v1, sn4ps3v3w4x5y6z7
Create Date: 2026-07-22 14:00:26.487903

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b27ee7b3c853'
down_revision: Union[str, Sequence[str], None] = ('q6r7s8t9u0v1', 'sn4ps3v3w4x5y6z7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
