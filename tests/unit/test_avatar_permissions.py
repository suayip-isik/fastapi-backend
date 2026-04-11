"""Avatar permission policy testleri."""

from app.api.policies.permissions import can_manage_other_users_avatar
from app.core.permissions import Permission
from app.db.models.user import SurfaceType


def test_can_manage_other_users_avatar_requires_admin_surface() -> None:
    perms = {Permission.USERS_MANAGE_AVATAR.value}

    assert can_manage_other_users_avatar(SurfaceType.CLIENT.value, perms) is False


def test_can_manage_other_users_avatar_requires_explicit_permission() -> None:
    perms = {Permission.ADMIN_PANEL_ACCESS.value}

    assert can_manage_other_users_avatar(SurfaceType.ADMIN.value, perms) is False


def test_can_manage_other_users_avatar_allows_admin_surface_with_permission() -> None:
    perms = {
        Permission.ADMIN_PANEL_ACCESS.value,
        Permission.USERS_MANAGE_AVATAR.value,
    }

    assert can_manage_other_users_avatar(SurfaceType.ADMIN.value, perms) is True
