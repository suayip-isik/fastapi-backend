"""Permission sabitleri — kaynak:aksiyon formatında RBAC yetkileri."""

from __future__ import annotations

from enum import Enum as PyEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


class Permission(str, PyEnum):
    """Sistemdeki tüm yetki tanımları.

    Format: "kaynak:aksiyon" (ör: "users:update").
    Roller bu enum değerlerinin kombinasyonlarına sahip olur.
    Yeni bir özellik eklendiğinde buraya permission eklenir,
    ardından ilgili rol(ler)e atanır — migration gerekmez.

    Attributes:
        ADMIN_PANEL_ACCESS: Admin paneline erişim
        USERS_LIST: Kullanıcı listesini görüntüleme
        USERS_VIEW: Kullanıcı detayını görüntüleme
        USERS_VIEW_STATS: Kullanıcı istatistiklerini görüntüleme
        USERS_LIST_DELETED: Silinmiş kullanıcıları görüntüleme
        USERS_CREATE_ADMIN: Admin kullanıcı oluşturma
        USERS_UPDATE: Kullanıcı bilgilerini güncelleme
        USERS_UPLOAD_AVATAR: Diğer kullanıcıların profil fotoğrafını yükleme
        USERS_DELETE_AVATAR: Diğer kullanıcıların profil fotoğrafını silme
        USERS_CHANGE_EMAIL: Kullanıcı e-posta adresini değiştirme
        USERS_RESEND_VERIFICATION: Kullanıcıya doğrulama e-postası yeniden gönderme
        USERS_RESEND_ADMIN_INVITE: Admin davetini yeniden gönderme
        USERS_ACTIVATE: Kullanıcıyı aktif etme
        USERS_DEACTIVATE: Kullanıcıyı pasif etme
        USERS_ASSIGN_ROLE: Kullanıcı rolünü değiştirme
        USERS_DELETE: Kullanıcıyı silme
        USERS_RESTORE: Kullanıcıyı geri yükleme
        ROLES_LIST: Rol listesini görüntüleme
        ROLES_VIEW: Rol detayını görüntüleme
        ROLES_CREATE: Rol oluşturma
        ROLES_UPDATE: Rol güncelleme
        ROLES_DELETE: Rol silme
        AUDIT_LIST: Audit log listesini görüntüleme
        AUDIT_STREAM: Audit log akışını görüntüleme
        AUDIT_VIEW: Audit log detayını görüntüleme
        API_KEYS_LIST: API key listesini görüntüleme
        API_KEYS_CREATE: API key oluşturma
        API_KEYS_REVOKE: API key silme
        NOTIFICATIONS_LIST: Bildirimleri görüntüleme
        NOTIFICATIONS_VIEW_UNREAD_COUNT: Okunmamış bildirim sayısını görüntüleme
        NOTIFICATIONS_MARK_ALL_READ: Tüm bildirimleri okundu işaretleme
        NOTIFICATIONS_MARK_READ: Tek bildirimi okundu işaretleme
        NOTIFICATIONS_DELETE: Bildirimi silme
        PROFILE_VIEW: Kendi profilini görüntüleme
        PROFILE_UPDATE: Kendi profilini güncelleme
        PROFILE_UPLOAD_AVATAR: Kendi profil fotoğrafını yükleme
        PROFILE_DELETE_AVATAR: Kendi profil fotoğrafını silme
    """

    # Admin
    ADMIN_PANEL_ACCESS = "admin:panel_access"

    # Users
    USERS_LIST = "users:list"
    USERS_VIEW = "users:view"
    USERS_VIEW_STATS = "users:view_stats"
    USERS_LIST_DELETED = "users:list_deleted"
    USERS_CREATE_ADMIN = "users:create_admin"
    USERS_UPDATE = "users:update"
    USERS_UPLOAD_AVATAR = "users:upload_avatar"
    USERS_DELETE_AVATAR = "users:delete_avatar"
    USERS_CHANGE_EMAIL = "users:change_email"
    USERS_RESEND_VERIFICATION = "users:resend_verification"
    USERS_RESEND_ADMIN_INVITE = "users:resend_admin_invite"
    USERS_ACTIVATE = "users:activate"
    USERS_DEACTIVATE = "users:deactivate"
    USERS_ASSIGN_ROLE = "users:assign_role"
    USERS_DELETE = "users:delete"
    USERS_RESTORE = "users:restore"

    # Roles
    ROLES_LIST = "roles:list"
    ROLES_VIEW = "roles:view"
    ROLES_CREATE = "roles:create"
    ROLES_UPDATE = "roles:update"
    ROLES_DELETE = "roles:delete"

    # Audit
    AUDIT_LIST = "audit:list"
    AUDIT_STREAM = "audit:stream"
    AUDIT_VIEW = "audit:view"

    # API Keys
    API_KEYS_LIST = "api_keys:list"
    API_KEYS_CREATE = "api_keys:create"
    API_KEYS_REVOKE = "api_keys:revoke"

    # Notifications
    NOTIFICATIONS_LIST = "notifications:list"
    NOTIFICATIONS_VIEW_UNREAD_COUNT = "notifications:view_unread_count"
    NOTIFICATIONS_MARK_ALL_READ = "notifications:mark_all_read"
    NOTIFICATIONS_MARK_READ = "notifications:mark_read"
    NOTIFICATIONS_DELETE = "notifications:delete"

    # Self-service (tüm authenticated kullanıcılar)
    PROFILE_VIEW = "profile:view"
    PROFILE_UPDATE = "profile:update"
    PROFILE_UPLOAD_AVATAR = "profile:upload_avatar"
    PROFILE_DELETE_AVATAR = "profile:delete_avatar"


# Sistem rolleri için permission setleri — seed ve test için kullanılır
PANEL_ADMIN_PERMISSIONS: list[Permission] = list(Permission)

APP_USER_PERMISSIONS: list[Permission] = [
    Permission.PROFILE_VIEW,
    Permission.PROFILE_UPDATE,
    Permission.PROFILE_UPLOAD_AVATAR,
    Permission.PROFILE_DELETE_AVATAR,
    Permission.API_KEYS_LIST,
    Permission.API_KEYS_CREATE,
    Permission.API_KEYS_REVOKE,
    Permission.NOTIFICATIONS_LIST,
    Permission.NOTIFICATIONS_VIEW_UNREAD_COUNT,
    Permission.NOTIFICATIONS_MARK_ALL_READ,
    Permission.NOTIFICATIONS_MARK_READ,
    Permission.NOTIFICATIONS_DELETE,
]


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


def has_admin_panel_access(permission_values: set[str]) -> bool:
    """Permission seti admin panel erişimini veriyor mu?"""
    return Permission.ADMIN_PANEL_ACCESS.value in permission_values
