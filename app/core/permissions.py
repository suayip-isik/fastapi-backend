"""Permission sabitleri — kaynak.aksiyon.kapsam formatında RBAC yetkileri."""

from __future__ import annotations

from enum import Enum as PyEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


class Permission(str, PyEnum):
    """Sistemdeki tüm yetki tanımları.

    Format: "resource.action.scope" (ör: "users.update.profile").
    Roller bu enum değerlerinin kombinasyonlarına sahip olur.
    Yeni bir özellik eklendiğinde buraya permission eklenir,
    ardından ilgili rol(ler)e atanır — migration gerekmez.
    """

    # Shared self-service
    PROFILE_READ_SELF = "profile.read.self"
    PROFILE_UPDATE_BASIC = "profile.update.basic"
    PROFILE_UPDATE_EMAIL = "profile.update.email"
    PROFILE_UPDATE_PASSWORD = "profile.update.password"  # noqa: S105
    PROFILE_UPDATE_AVATAR = "profile.update.avatar"
    PROFILE_DELETE_AVATAR = "profile.delete.avatar"

    # Shared uploads
    UPLOADS_CREATE_OWN = "uploads.create.own"
    UPLOADS_DELETE_OWN = "uploads.delete.own"
    UPLOADS_DELETE_ANY = "uploads.delete.any"

    # Users admin surface
    USERS_LIST = "users.list"
    USERS_READ_BASIC = "users.read.basic"
    USERS_READ_DELETED = "users.read.deleted"
    USERS_READ_STATS = "users.read.stats"
    USERS_CREATE_ADMIN = "users.create.admin"
    USERS_UPDATE_PROFILE = "users.update.profile"
    USERS_UPDATE_EMAIL = "users.update.email"
    USERS_UPDATE_ROLE = "users.update.role"
    USERS_UPDATE_AVATAR = "users.update.avatar"
    USERS_DELETE_AVATAR = "users.delete.avatar"
    USERS_RESEND_VERIFICATION = "users.resend.verification"
    USERS_RESEND_ADMIN_INVITE = "users.resend.admin_invite"
    USERS_ACTIVATE = "users.activate"
    USERS_DEACTIVATE = "users.deactivate"
    USERS_DELETE = "users.delete"
    USERS_RESTORE = "users.restore"

    # Roles
    ROLES_LIST = "roles.list"
    ROLES_READ_DETAIL = "roles.read.detail"
    ROLES_CREATE = "roles.create"
    ROLES_UPDATE_DESCRIPTION = "roles.update.description"
    ROLES_UPDATE_PERMISSIONS = "roles.update.permissions"
    ROLES_DELETE = "roles.delete"

    # Audit logs
    AUDIT_LOGS_LIST = "audit_logs.list"
    AUDIT_LOGS_STREAM = "audit_logs.stream"
    AUDIT_LOGS_READ_DETAIL = "audit_logs.read.detail"

    # API Keys
    API_KEYS_LIST = "api_keys.list"
    API_KEYS_CREATE = "api_keys.create"
    API_KEYS_REVOKE = "api_keys.revoke"

    # Notifications
    NOTIFICATIONS_LIST = "notifications.list"
    NOTIFICATIONS_READ_UNREAD_COUNT = "notifications.read.unread_count"
    NOTIFICATIONS_UPDATE_ALL_READ = "notifications.update.all_read"
    NOTIFICATIONS_UPDATE_READ = "notifications.update.read"
    NOTIFICATIONS_DELETE = "notifications.delete"


# Sistem rolleri için permission setleri — seed ve test için kullanılır
PANEL_ADMIN_PERMISSIONS: list[Permission] = list(Permission)

APP_USER_PERMISSIONS: list[Permission] = [
    Permission.PROFILE_READ_SELF,
    Permission.PROFILE_UPDATE_BASIC,
    Permission.PROFILE_UPDATE_EMAIL,
    Permission.PROFILE_UPDATE_PASSWORD,
    Permission.PROFILE_UPDATE_AVATAR,
    Permission.PROFILE_DELETE_AVATAR,
    Permission.UPLOADS_CREATE_OWN,
    Permission.UPLOADS_DELETE_OWN,
    Permission.API_KEYS_LIST,
    Permission.API_KEYS_CREATE,
    Permission.API_KEYS_REVOKE,
    Permission.NOTIFICATIONS_LIST,
    Permission.NOTIFICATIONS_READ_UNREAD_COUNT,
    Permission.NOTIFICATIONS_UPDATE_ALL_READ,
    Permission.NOTIFICATIONS_UPDATE_READ,
    Permission.NOTIFICATIONS_DELETE,
]

ADMIN_SURFACE_PERMISSIONS: frozenset[str] = frozenset(
    {
        Permission.UPLOADS_DELETE_ANY.value,
        Permission.USERS_LIST.value,
        Permission.USERS_READ_BASIC.value,
        Permission.USERS_READ_DELETED.value,
        Permission.USERS_READ_STATS.value,
        Permission.USERS_CREATE_ADMIN.value,
        Permission.USERS_UPDATE_PROFILE.value,
        Permission.USERS_UPDATE_EMAIL.value,
        Permission.USERS_UPDATE_ROLE.value,
        Permission.USERS_UPDATE_AVATAR.value,
        Permission.USERS_DELETE_AVATAR.value,
        Permission.USERS_RESEND_VERIFICATION.value,
        Permission.USERS_RESEND_ADMIN_INVITE.value,
        Permission.USERS_ACTIVATE.value,
        Permission.USERS_DEACTIVATE.value,
        Permission.USERS_DELETE.value,
        Permission.USERS_RESTORE.value,
        Permission.ROLES_LIST.value,
        Permission.ROLES_READ_DETAIL.value,
        Permission.ROLES_CREATE.value,
        Permission.ROLES_UPDATE_DESCRIPTION.value,
        Permission.ROLES_UPDATE_PERMISSIONS.value,
        Permission.ROLES_DELETE.value,
        Permission.AUDIT_LOGS_LIST.value,
        Permission.AUDIT_LOGS_STREAM.value,
        Permission.AUDIT_LOGS_READ_DETAIL.value,
    }
)


VALID_PERMISSION_VALUES: frozenset[str] = frozenset(permission.value for permission in Permission)


def normalize_permission_value(permission: Permission | str) -> str:
    """Permission enum/string girdisini canonical string değere çevirir."""
    return permission.value if isinstance(permission, Permission) else permission


def find_invalid_permissions(permissions: Iterable[Permission | str]) -> list[str]:
    """Canonical sözlükte olmayan permission değerlerini döndürür."""
    invalid: list[str] = []
    for permission in permissions:
        value = normalize_permission_value(permission)
        if value not in VALID_PERMISSION_VALUES and value not in invalid:
            invalid.append(value)
    return invalid


def has_admin_surface_access(permission_values: set[str]) -> bool:
    """Permission seti admin surface üzerinde en az bir route/action verir mi?"""
    return bool(permission_values & ADMIN_SURFACE_PERMISSIONS)
