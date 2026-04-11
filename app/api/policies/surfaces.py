"""Surface bazlı erişim policy'leri."""

from __future__ import annotations

from app.api.surfaces import Surface
from app.db.models.user import SurfaceType


def can_access_surface(user_surface: str, target_surface: Surface) -> bool:
    """Belirli user surface verilen API surface'ine erişebilir mi?"""
    if target_surface is Surface.SHARED:
        return True
    if target_surface is Surface.ADMIN:
        return user_surface == SurfaceType.ADMIN.value
    return user_surface == SurfaceType.CLIENT.value
