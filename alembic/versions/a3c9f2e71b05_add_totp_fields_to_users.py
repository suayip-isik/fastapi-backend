"""add totp fields to users

Revision ID: a3c9f2e71b05
Revises: dd1a494e6840
Create Date: 2026-03-29 10:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a3c9f2e71b05'
down_revision: Union[str, None] = 'dd1a494e6840'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Users tablosuna totp_secret ve totp_enabled alanlarını ekler."""
    op.add_column('users', sa.Column('totp_secret', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('totp_enabled', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    """Users tablosundan TOTP alanlarını kaldırır."""
    op.drop_column('users', 'totp_enabled')
    op.drop_column('users', 'totp_secret')
