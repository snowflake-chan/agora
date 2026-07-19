"""fix report FK to SET NULL instead of CASCADE

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-20 00:30:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('report_content_id_fkey', 'report', type_='foreignkey')
    op.create_foreign_key(
        'report_content_id_fkey', 'report', 'content',
        ['content_id'], ['id'], ondelete='SET NULL'
    )
    op.alter_column('report', 'content_id', nullable=True)


def downgrade() -> None:
    op.drop_constraint('report_content_id_fkey', 'report', type_='foreignkey')
    op.create_foreign_key(
        'report_content_id_fkey', 'report', 'content',
        ['content_id'], ['id'], ondelete='CASCADE'
    )
    op.alter_column('report', 'content_id', nullable=False)
