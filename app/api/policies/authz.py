"""Authorization kararlarını exception ile ifade eden helper'lar."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.api.policies.permissions import has_permissions_all, has_permissions_any
from app.api.policies.surfaces import can_access_surface
from app.core.exceptions import InsufficientPermissionsError
from app.core.i18n import t

if TYPE_CHECKING:
    from app.api.surfaces import Surface
    from app.core.permissions import Permission


def ensure_surface_access(user_surface: str, target_surface: Surface) -> None:
    """Surface erişimi yoksa exception fırlat."""
    if not can_access_surface(user_surface, target_surface):
        raise InsufficientPermissionsError(t("error.permissions.surface_forbidden"))


def ensure_permissions_all(effective_permissions: set[str], *perms: Permission) -> None:
    """Tüm permission'lar mevcut değilse exception fırlat."""
    if not has_permissions_all(effective_permissions, perms):
        raise InsufficientPermissionsError(
            t("error.permissions.required_all", permissions=", ".join(p.value for p in perms))
        )


def ensure_permissions_any(effective_permissions: set[str], *perms: Permission) -> None:
    """Gerekli permission'lardan hiçbiri yoksa exception fırlat."""
    if not has_permissions_any(effective_permissions, perms):
        raise InsufficientPermissionsError(
            t("error.permissions.required_any", permissions=", ".join(p.value for p in perms))
        )
