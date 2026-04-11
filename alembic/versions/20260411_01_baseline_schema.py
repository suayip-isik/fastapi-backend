"""baseline schema

Revision ID: 20260411_01
Revises:
Create Date: 2026-04-11 15:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260411_01"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Bugünkü uygulama şemasını tek baseline migration ile kurar."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "roles",
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_roles_deleted_at", "roles", ["deleted_at"], unique=False)
    op.create_index(
        "ix_roles_name_active",
        "roles",
        ["name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "users",
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("pending_email", sa.String(length=255), nullable=True),
        sa.Column("username", sa.String(length=50), nullable=True),
        sa.Column("hashed_password", sa.Text(), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("surface", sa.String(length=20), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("session_revoked_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("totp_secret", sa.Text(), nullable=True),
        sa.Column("totp_enabled", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"], unique=False)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.execute("CREATE INDEX ix_users_email_trgm ON users USING gin (email gin_trgm_ops)")
    op.create_index("ix_users_filters", "users", ["role_id", "is_active", "is_verified", "deleted_at"], unique=False)
    op.execute("CREATE INDEX ix_users_full_name_trgm ON users USING gin (full_name gin_trgm_ops)")
    op.create_index("ix_users_pending_email", "users", ["pending_email"], unique=True)
    op.create_index("ix_users_role_id", "users", ["role_id"], unique=False)
    op.create_index("ix_users_surface", "users", ["surface"], unique=False)
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.execute("CREATE INDEX ix_users_username_trgm ON users USING gin (username gin_trgm_ops)")

    op.create_table(
        "audit_logs",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "action",
            sa.Enum(
                "login_success",
                "login_failed",
                "logout",
                "register",
                "email_verified",
                "email_change_requested",
                "email_changed",
                "verification_resent",
                "password_reset_requested",
                "password_reset",
                "admin_password_reset_requested",
                "admin_password_reset",
                "token_refreshed",
                "profile_updated",
                "user_deactivated",
                "user_activated",
                "role_changed",
                "admin_user_created",
                "admin_invite_resent",
                "user_management_blocked",
                "user_deleted",
                "user_restored",
                "password_changed",
                "account_deleted",
                "file_uploaded",
                "file_deleted",
                "api_key_created",
                "api_key_revoked",
                "api_key_used",
                "totp_setup_started",
                "totp_enabled",
                "totp_disabled",
                "totp_backup_codes_regenerated",
                "role_created",
                "role_updated",
                "role_deleted",
                "notification_read",
                "notification_deleted",
                name="auditaction",
            ),
            nullable=False,
        ),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_action_created", "audit_logs", ["action", "created_at"], unique=False)
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"], unique=False)
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"], unique=False)
    op.create_index("ix_audit_user_created", "audit_logs", ["user_id", "created_at"], unique=False)

    op.create_table(
        "api_keys",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("key_prefix", sa.String(length=12), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "key_prefix", name="uq_api_key_user_prefix"),
    )
    op.create_index("ix_api_keys_user_active", "api_keys", ["user_id", "is_active"], unique=False)
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "info",
                "success",
                "warning",
                "error",
                "system",
                "mention",
                "file_processed",
                name="notificationtype",
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"], unique=False)
    op.create_index("ix_notifications_user_created", "notifications", ["user_id", "created_at"], unique=False)
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"], unique=False)
    op.create_index("ix_notifications_user_read", "notifications", ["user_id", "is_read"], unique=False)

    op.create_table(
        "role_permissions",
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "permission"),
    )

    op.create_table(
        "totp_backup_codes",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code_hash", sa.Text(), nullable=False),
        sa.Column("is_used", sa.Boolean(), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "code_hash", name="uq_totp_backup_user_hash"),
    )
    op.create_index("ix_totp_backup_code_hash", "totp_backup_codes", ["user_id", "code_hash"], unique=False)
    op.create_index("ix_totp_backup_codes_user_id", "totp_backup_codes", ["user_id"], unique=False)
    op.create_index("ix_totp_backup_user_used", "totp_backup_codes", ["user_id", "is_used"], unique=False)


def downgrade() -> None:
    """Baseline şemasını geri alır."""
    op.drop_index("ix_totp_backup_user_used", table_name="totp_backup_codes")
    op.drop_index("ix_totp_backup_codes_user_id", table_name="totp_backup_codes")
    op.drop_index("ix_totp_backup_code_hash", table_name="totp_backup_codes")
    op.drop_table("totp_backup_codes")

    op.drop_table("role_permissions")

    op.drop_index("ix_notifications_user_read", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_index("ix_notifications_is_read", table_name="notifications")
    op.drop_table("notifications")

    op.drop_index("ix_api_keys_user_id", table_name="api_keys")
    op.drop_index("ix_api_keys_user_active", table_name="api_keys")
    op.drop_table("api_keys")

    op.drop_index("ix_audit_user_created", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_action_created", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.execute("DROP INDEX IF EXISTS ix_users_username_trgm")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_surface", table_name="users")
    op.drop_index("ix_users_role_id", table_name="users")
    op.drop_index("ix_users_pending_email", table_name="users")
    op.execute("DROP INDEX IF EXISTS ix_users_full_name_trgm")
    op.drop_index("ix_users_filters", table_name="users")
    op.execute("DROP INDEX IF EXISTS ix_users_email_trgm")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_deleted_at", table_name="users")
    op.drop_table("users")

    op.drop_index("ix_roles_name_active", table_name="roles")
    op.drop_index("ix_roles_deleted_at", table_name="roles")
    op.drop_table("roles")

    op.execute("DROP TYPE IF EXISTS notificationtype")
    op.execute("DROP TYPE IF EXISTS auditaction")
