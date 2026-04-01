"""add user soft delete

Revision ID: f3a8b1c05d20
Revises: e1f7a2c94b06
Create Date: 2026-04-01 01:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f3a8b1c05d20"
down_revision: Union[str, None] = "e1f7a2c94b06"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"])
    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'user_deleted'")
    op.execute("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'user_restored'")


def downgrade() -> None:
    op.drop_index("ix_users_deleted_at", table_name="users")
    op.drop_column("users", "deleted_at")
    # PostgreSQL enum değeri silmeyi desteklemez.
