"""roles: add soft-delete support

Revision ID: c6d7e8f9a0b1
Revises: b3c4d5e6f7a8
Create Date: 2026-04-05 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c6d7e8f9a0b1"
down_revision: Union[str, None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "roles",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_roles_deleted_at", "roles", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_roles_deleted_at", table_name="roles")
    op.drop_column("roles", "deleted_at")
