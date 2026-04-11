"""add password_changed and account_deleted audit actions

Revision ID: d9f3b2e01c47
Revises: ba36edc854a4
Branch Labels: None
Depends On: None

Create Date: 2026-04-01 14:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = 'd9f3b2e01c47'
down_revision: Union[str, None] = 'ba36edc854a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """AuditAction enum'ına password_changed ve account_deleted değerlerini ekler."""
    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'password_changed'")
    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'account_deleted'")


def downgrade() -> None:
    """PostgreSQL enum değeri silmeyi desteklemez, bu yüzden işlem yapılmaz."""
    # PostgreSQL enum değeri silmeyi desteklemez.
    pass
