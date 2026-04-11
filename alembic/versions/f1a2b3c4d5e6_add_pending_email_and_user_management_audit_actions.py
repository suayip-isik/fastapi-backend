"""add pending email and user management audit actions

Revision ID: f1a2b3c4d5e6
Revises: e4f5a6b7c8d9
Create Date: 2026-04-11 14:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Users tablosuna pending_email ve yeni audit action'ları ekler."""
    op.add_column("users", sa.Column("pending_email", sa.String(length=255), nullable=True))
    op.create_index("ix_users_pending_email", "users", ["pending_email"], unique=True)
    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'email_change_requested'")
    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'email_changed'")
    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'verification_resent'")
    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'user_management_blocked'")


def downgrade() -> None:
    """Enum değerleri geri alınamaz; yalnız yeni kolon ve index kaldırılır."""
    op.drop_index("ix_users_pending_email", table_name="users")
    op.drop_column("users", "pending_email")
