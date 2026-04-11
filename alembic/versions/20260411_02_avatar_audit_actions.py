"""add avatar audit actions

Revision ID: 20260411_02
Revises: 20260411_01
Create Date: 2026-04-11 18:30:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260411_02"
down_revision: Union[str, None] = "20260411_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """AuditAction enum'una avatar action'larını ekler."""
    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'profile_avatar_uploaded'")
    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'profile_avatar_updated'")
    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'profile_avatar_deleted'")


def downgrade() -> None:
    """PostgreSQL enum value silmeyi desteklemediğinden no-op."""
    pass
