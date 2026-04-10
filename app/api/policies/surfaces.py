"""Surface bazlı erişim policy'leri."""

from __future__ import annotations

from app.api.surfaces import Surface
from app.db.models.user import AccountType


def can_access_surface(account_type: str, surface: Surface) -> bool:
    """Belirli account_type verilen surface'e erişebilir mi?"""
    if surface is Surface.SHARED:
        return True
    if surface is Surface.ADMIN:
        return account_type == AccountType.ADMIN.value
    return account_type == AccountType.CLIENT.value
