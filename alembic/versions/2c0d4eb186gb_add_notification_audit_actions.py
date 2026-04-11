"""add_notification_audit_actions

Revision ID: 2c0d4eb186gb
Revises: 1b9a3da075fa
Create Date: 2026-04-07 22:30:00.000000
"""
from __future__ import annotations
from typing import Sequence, Union
from alembic import op

revision: str = '2c0d4eb186gb'
down_revision: Union[str, None] = '1b9a3da075fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_ACTIONS = ["notification_read", "notification_deleted"]


def upgrade() -> None:
    for action in NEW_ACTIONS:
        op.execute(f"ALTER TYPE auditaction ADD VALUE IF NOT EXISTS '{action}'")


def downgrade() -> None:
    pass  # PostgreSQL enum değerleri kaldırılamaz
