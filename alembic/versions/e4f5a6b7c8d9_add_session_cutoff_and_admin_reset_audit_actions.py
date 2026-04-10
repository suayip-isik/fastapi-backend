"""add session cutoff and admin reset audit actions

Revision ID: e4f5a6b7c8d9
Revises: c1d2e3f4a5b6
Create Date: 2026-04-11 13:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Kullanıcı bazlı session cutoff alanını ve admin reset audit action'larını ekler."""
    op.add_column(
        "users",
        sa.Column("session_revoked_after", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'admin_password_reset_requested'")
    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'admin_password_reset'")


def downgrade() -> None:
    """Enum değerleri geri alınamaz; yalnız yeni kolon kaldırılır."""
    op.drop_column("users", "session_revoked_after")
