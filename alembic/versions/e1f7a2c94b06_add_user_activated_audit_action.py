"""add user_activated audit action

Revision ID: e1f7a2c94b06
Revises: c5e8a3d14f29
Create Date: 2026-04-01 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = 'e1f7a2c94b06'
down_revision: Union[str, None] = 'c5e8a3d14f29'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """AuditAction enum'ına user_activated değerini ekler."""
    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'user_activated'")


def downgrade() -> None:
    """PostgreSQL enum değeri silmeyi desteklemez, bu yüzden işlem yapılmaz."""
    # PostgreSQL enum değeri silmeyi desteklemez.
    pass
