"""Permission tabanlı authorization helper'ları."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.permissions import Permission, has_admin_panel_access
from app.db.models.user import SurfaceType

if TYPE_CHECKING:
    from collections.abc import Iterable


def _normalize_permissions(required: Iterable[Permission | str]) -> set[str]:
    return {perm.value if isinstance(perm, Permission) else perm for perm in required}


def has_permissions_all(
    effective_permissions: set[str],
    required_permissions: Iterable[Permission | str],
) -> bool:
    """Tüm gerekli permission'lar mevcut mu?"""
    required = _normalize_permissions(required_permissions)
    return required.issubset(effective_permissions)


def has_permissions_any(
    effective_permissions: set[str],
    required_permissions: Iterable[Permission | str],
) -> bool:
    """Gerekli permission'lardan en az biri mevcut mu?"""
    required = _normalize_permissions(required_permissions)
    return bool(required & effective_permissions)


def can_delete_any_uploaded_file(surface: str, effective_permissions: set[str]) -> bool:
    """Kullanıcı herhangi bir upload dosyasını silebilir mi?"""
    return surface == SurfaceType.ADMIN.value and has_admin_panel_access(effective_permissions)


def can_manage_other_users_avatar(surface: str, effective_permissions: set[str]) -> bool:
    """Kullanıcı başka kullanıcıların avatarını yönetebilir mi?"""
    return surface == SurfaceType.ADMIN.value and has_permissions_any(
        effective_permissions,
        [Permission.USERS_UPLOAD_AVATAR, Permission.USERS_DELETE_AVATAR],
    )
