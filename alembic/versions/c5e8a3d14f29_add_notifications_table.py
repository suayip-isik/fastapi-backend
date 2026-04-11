"""add notifications table

Revision ID: c5e8a3d14f29
Revises: b7d1e4f92a38
Create Date: 2026-03-29 10:10:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'c5e8a3d14f29'
down_revision: Union[str, None] = 'b7d1e4f92a38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Bildirim sistemi için notifications tablosunu oluşturur."""
    op.create_table(
        'notifications',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            'type',
            sa.Enum(
                'info', 'success', 'warning', 'error', 'system', 'mention', 'file_processed',
                name='notificationtype',
            ),
            nullable=False,
            server_default='info',
        ),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)
    op.create_index(op.f('ix_notifications_is_read'), 'notifications', ['is_read'], unique=False)


def downgrade() -> None:
    """notifications tablosunu ve notificationtype enum'ını siler."""
    op.drop_index(op.f('ix_notifications_is_read'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_table('notifications')
    op.execute("DROP TYPE IF EXISTS notificationtype")
