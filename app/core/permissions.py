"""Permission sabitleri — kaynak:aksiyon formatında RBAC yetkileri."""

from __future__ import annotations

from enum import Enum as PyEnum


class Permission(str, PyEnum):
    """Sistemdeki tüm yetki tanımları.

    Format: "kaynak:aksiyon" (ör: "users:write").
    Roller bu enum değerlerinin kombinasyonlarına sahip olur.
    Yeni bir özellik eklendiğinde buraya permission eklenir,
    ardından ilgili rol(ler)e atanır — migration gerekmez.

    Attributes:
        ADMIN_PANEL_ACCESS: Admin paneline erişim
        USERS_CREATE_ADMIN: Admin kullanıcı oluşturma ve davet yeniden gönderme
        USERS_READ: Kullanıcı listesini görüntüleme
        USERS_WRITE: Kullanıcı bilgilerini güncelleme
        USERS_DELETE: Kullanıcıyı silme / geri yükleme
        ROLES_READ: Rol listesini görüntüleme
        ROLES_WRITE: Rol oluşturma, güncelleme, silme
        AUDIT_READ: Audit logları görüntüleme
        API_KEYS_READ: API key listesini görüntüleme
        API_KEYS_WRITE: API key oluşturma ve silme
        NOTIFICATIONS_READ: Bildirimleri görüntüleme
        PROFILE_READ: Kendi profilini görüntüleme
        PROFILE_WRITE: Kendi profilini güncelleme
    """

    # Admin
    ADMIN_PANEL_ACCESS = "admin:panel_access"

    # Users
    USERS_CREATE_ADMIN = "users:create_admin"
    USERS_READ = "users:read"
    USERS_WRITE = "users:write"
    USERS_DELETE = "users:delete"

    # Roles
    ROLES_READ = "roles:read"
    ROLES_WRITE = "roles:write"

    # Audit
    AUDIT_READ = "audit:read"

    # API Keys
    API_KEYS_READ = "api_keys:read"
    API_KEYS_WRITE = "api_keys:write"

    # Notifications
    NOTIFICATIONS_READ = "notifications:read"

    # Self-service (tüm authenticated kullanıcılar)
    PROFILE_READ = "profile:read"
    PROFILE_WRITE = "profile:write"


# Sistem rolleri için permission setleri — seed ve test için kullanılır
ADMIN_PERMISSIONS: list[Permission] = list(Permission)

USER_PERMISSIONS: list[Permission] = [
    Permission.PROFILE_READ,
    Permission.PROFILE_WRITE,
    Permission.API_KEYS_READ,
    Permission.API_KEYS_WRITE,
    Permission.NOTIFICATIONS_READ,
]

MODERATOR_PERMISSIONS: list[Permission] = [
    Permission.PROFILE_READ,
    Permission.PROFILE_WRITE,
    Permission.USERS_READ,
    Permission.AUDIT_READ,
    Permission.NOTIFICATIONS_READ,
]


def has_admin_panel_access(permission_values: set[str]) -> bool:
    """Permission seti admin panel erişimini veriyor mu?"""
    return Permission.ADMIN_PANEL_ACCESS.value in permission_values
