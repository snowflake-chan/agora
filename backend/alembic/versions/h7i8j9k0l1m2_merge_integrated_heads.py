"""merge the main content history with guild and moderation

Revision ID: h7i8j9k0l1m2
Revises: c034f9e1a6b3, m001m3rg3h34ds
Create Date: 2026-07-20 12:00:00.000000

"""
from typing import Sequence, Union


revision: str = "h7i8j9k0l1m2"
down_revision: Union[str, Sequence[str], None] = (
    "c034f9e1a6b3",
    "m001m3rg3h34ds",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
