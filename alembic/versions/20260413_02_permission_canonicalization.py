"""Canonicalize role_permissions permission values to dot notation.

Revision ID: 20260413_02
Revises: 20260413_01
Create Date: 2026-04-13
"""

from __future__ import annotations

from collections.abc import Iterable

import sqlalchemy as sa
from alembic import op

from app.core.permissions import Permission

# revision identifiers, used by Alembic.
revision = "20260413_02"
down_revision = "20260413_01"
branch_labels = None
depends_on = None


LEGACY_TO_CANONICAL: dict[str, str] = {
    "profile:view": "profile.read.self",
    "profile:update": "profile.update.basic",
    "profile:upload_avatar": "profile.update.avatar",
    "profile:delete_avatar": "profile.delete.avatar",
    "users:list": "users.list",
    "users:view": "users.read.basic",
    "users:view_stats": "users.read.stats",
    "users:list_deleted": "users.read.deleted",
    "users:create_admin": "users.create.admin",
    "users:update": "users.update.profile",
    "users:upload_avatar": "users.update.avatar",
    "users:delete_avatar": "users.delete.avatar",
    "users:change_email": "users.update.email",
    "users:resend_verification": "users.resend.verification",
    "users:resend_admin_invite": "users.resend.admin_invite",
    "users:activate": "users.activate",
    "users:deactivate": "users.deactivate",
    "users:assign_role": "users.update.role",
    "users:delete": "users.delete",
    "users:restore": "users.restore",
    "roles:list": "roles.list",
    "roles:view": "roles.read.detail",
    "roles:create": "roles.create",
    "roles:update": "roles.update.permissions",
    "roles:delete": "roles.delete",
    "audit:list": "audit_logs.list",
    "audit:stream": "audit_logs.stream",
    "audit:view": "audit_logs.read.detail",
    "api_keys:list": "api_keys.list",
    "api_keys:create": "api_keys.create",
    "api_keys:revoke": "api_keys.revoke",
    "notifications:list": "notifications.list",
    "notifications:view_unread_count": "notifications.read.unread_count",
    "notifications:mark_all_read": "notifications.update.all_read",
    "notifications:mark_read": "notifications.update.read",
    "notifications:delete": "notifications.delete",
    "admin:panel_access": "uploads.delete.any",
}


def _table_permissions() -> list[str]:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT DISTINCT permission FROM role_permissions WHERE permission IS NOT NULL")
    )
    return sorted({row[0] for row in rows})


def _find_unknown_permissions(permissions: Iterable[str]) -> list[str]:
    valid = {permission.value for permission in Permission}
    unknown: list[str] = []
    for permission in permissions:
        mapped = LEGACY_TO_CANONICAL.get(permission, permission)
        if mapped not in valid and permission not in unknown:
            unknown.append(permission)
    return unknown


def upgrade() -> None:
    bind = op.get_bind()

    existing_permissions = _table_permissions()
    unknown_permissions = _find_unknown_permissions(existing_permissions)
    if unknown_permissions:
        raise RuntimeError(
            "role_permissions tablosunda dönüştürülemeyen permission değerleri var: "
            + ", ".join(unknown_permissions)
        )

    op.execute(
        """
        ALTER TABLE role_permissions
        ALTER COLUMN permission TYPE VARCHAR(100)
        USING permission::text
        """
    )
    op.execute("DROP TYPE IF EXISTS permissionenum")

    for legacy_permission, canonical_permission in LEGACY_TO_CANONICAL.items():
        bind.execute(
            sa.text(
                """
                UPDATE role_permissions
                SET permission = :canonical_permission
                WHERE permission = :legacy_permission
                """
            ),
            {
                "legacy_permission": legacy_permission,
                "canonical_permission": canonical_permission,
            },
        )

    permission_enum = sa.Enum(
        *tuple(permission.value for permission in Permission),
        name="permissionenum",
    )
    permission_enum.create(bind, checkfirst=True)
    op.execute(
        """
        ALTER TABLE role_permissions
        ALTER COLUMN permission TYPE permissionenum
        USING permission::permissionenum
        """
    )


def downgrade() -> None:
    raise RuntimeError("Permission canonicalization migration is intentionally irreversible.")
