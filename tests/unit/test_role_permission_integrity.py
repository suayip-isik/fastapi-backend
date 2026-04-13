"""Role permission integrity guard testleri."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.permissions import Permission, find_invalid_permissions
from app.db.models.role import Role, RolePermission


def test_find_invalid_permissions_returns_unknown_values() -> None:
    invalid = find_invalid_permissions(
        [Permission.USERS_READ_BASIC, "users:read", "nope:perm", "users:read"]
    )

    assert invalid == ["users:read", "nope:perm"]


def test_role_permission_model_rejects_invalid_permission_value() -> None:
    with pytest.raises(ValueError, match="not a valid Permission"):
        RolePermission(role_id=uuid4(), permission="users:read")


def test_role_permission_model_accepts_enum_and_role_permission_set_returns_strings() -> None:
    role = Role(name="support", description="Support", is_system=False)
    role.permissions = [
        RolePermission(role_id=role.id, permission=Permission.USERS_READ_BASIC),
        RolePermission(role_id=role.id, permission=Permission.UPLOADS_DELETE_ANY.value),
    ]

    assert role.permission_set == {
        Permission.USERS_READ_BASIC.value,
        Permission.UPLOADS_DELETE_ANY.value,
    }
