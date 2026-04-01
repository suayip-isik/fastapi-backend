"""add totp backup codes table

Revision ID: a7c2e9f04b31
Revises: f3a8b1c05d20
Create Date: 2026-04-01 02:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a7c2e9f04b31"
down_revision: Union[str, None] = "f3a8b1c05d20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "totp_backup_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.Text, nullable=False),
        sa.Column("is_used", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_totp_backup_codes_user_id", "totp_backup_codes", ["user_id"])
    op.create_index(
        "ix_totp_backup_codes_user_active",
        "totp_backup_codes",
        ["user_id"],
        postgresql_where=sa.text("is_used = false"),
    )


def downgrade() -> None:
    op.drop_index("ix_totp_backup_codes_user_active", table_name="totp_backup_codes")
    op.drop_index("ix_totp_backup_codes_user_id", table_name="totp_backup_codes")
    op.drop_table("totp_backup_codes")
