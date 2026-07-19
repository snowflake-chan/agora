"""add moderation + guild approval

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-19 23:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('report',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('content_id', sa.Uuid(), nullable=False),
        sa.Column('reporter_id', sa.Uuid(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=True, server_default='pending'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['content_id'], ['content.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reporter_id'], ['user.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_report_content_id', 'report', ['content_id'])
    op.create_table('ban_record',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('target_user_id', sa.Uuid(), nullable=False),
        sa.Column('content_id', sa.Uuid(), nullable=True),
        sa.Column('type', sa.String(length=20), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('duration_hours', sa.Integer(), nullable=True),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.ForeignKeyConstraint(['content_id'], ['content.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['target_user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ban_record_target_user_id', 'ban_record', ['target_user_id'])
    op.add_column('guild_member', sa.Column('status', sa.String(length=20), nullable=True, server_default='approved'))


def downgrade() -> None:
    op.drop_column('guild_member', 'status')
    op.drop_index('ix_ban_record_target_user_id', table_name='ban_record')
    op.drop_table('ban_record')
    op.drop_index('ix_report_content_id', table_name='report')
    op.drop_table('report')
