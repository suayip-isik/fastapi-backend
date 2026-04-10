"""add account_type to users

Revision ID: f9a1b2c3d4e5
Revises: 5a3b7c1d9e2f
Create Date: 2026-04-10 10:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "f9a1b2c3d4e5"
down_revision = "5a3b7c1d9e2f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("account_type", sa.String(length=20), nullable=False, server_default="client"),
    )
    op.create_index(op.f("ix_users_account_type"), "users", ["account_type"], unique=False)

    op.execute(
        """
        UPDATE users
        SET account_type = 'admin'
        WHERE role_id IN (
            SELECT role_id FROM role_permissions
            WHERE permission IN ('admin:access', 'admin:panel_access')
        )
        """
    )

    op.alter_column("users", "account_type", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_account_type"), table_name="users")
    op.drop_column("users", "account_type")
