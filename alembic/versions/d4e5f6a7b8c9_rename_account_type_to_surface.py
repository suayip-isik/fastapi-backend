"""rename account_type to surface

Revision ID: d4e5f6a7b8c9
Revises: c1d2e3f4a5b6
Create Date: 2026-04-11 11:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_users_account_type", table_name="users")
    op.alter_column("users", "account_type", new_column_name="surface")
    op.create_index("ix_users_surface", "users", ["surface"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_users_surface", table_name="users")
    op.alter_column("users", "surface", new_column_name="account_type")
    op.create_index("ix_users_account_type", "users", ["account_type"], unique=False)
