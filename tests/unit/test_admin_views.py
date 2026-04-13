from __future__ import annotations

from types import SimpleNamespace

from app.admin.views import AuditLogAdmin, RoleAdmin, UserAdmin
from app.core.permissions import Permission


def _request(*permissions: str) -> SimpleNamespace:
    return SimpleNamespace(session={"admin_permissions": list(permissions)})


def test_user_admin_exposes_create_and_edit_for_panel_admin_permissions() -> None:
    view = UserAdmin()
    request = _request(
        Permission.USERS_LIST.value,
        Permission.USERS_READ_BASIC.value,
        Permission.USERS_CREATE_ADMIN.value,
        Permission.USERS_UPDATE_PROFILE.value,
        Permission.USERS_UPDATE_EMAIL.value,
        Permission.USERS_UPDATE_ROLE.value,
        Permission.USERS_DELETE.value,
    )

    assert view.is_accessible(request) is True
    assert view.can_create_for_request(request) is True
    assert view.can_edit_for_request(request) is True
    assert view.can_delete_for_request(request) is True
    assert view.can_view_details_for_request(request) is True


def test_user_admin_hides_edit_without_full_edit_permission_set() -> None:
    view = UserAdmin()
    request = _request(
        Permission.USERS_LIST.value,
        Permission.USERS_READ_BASIC.value,
        Permission.USERS_UPDATE_PROFILE.value,
        Permission.USERS_UPDATE_ROLE.value,
    )

    assert view.is_accessible(request) is True
    assert view.can_edit_for_request(request) is False


def test_role_admin_uses_create_and_description_permissions() -> None:
    view = RoleAdmin()
    request = _request(
        Permission.ROLES_LIST.value,
        Permission.ROLES_CREATE.value,
        Permission.ROLES_READ_DETAIL.value,
        Permission.ROLES_UPDATE_DESCRIPTION.value,
        Permission.ROLES_DELETE.value,
    )

    assert view.can_create_for_request(request) is True
    assert view.can_edit_for_request(request) is True
    assert view.can_delete_for_request(request) is True


def test_audit_log_admin_is_read_only() -> None:
    view = AuditLogAdmin()
    request = _request(
        Permission.AUDIT_LOGS_LIST.value,
        Permission.AUDIT_LOGS_READ_DETAIL.value,
        Permission.AUDIT_LOGS_STREAM.value,
    )

    assert view.is_accessible(request) is True
    assert view.can_create_for_request(request) is False
    assert view.can_edit_for_request(request) is False
    assert view.can_delete_for_request(request) is False
    assert view.can_view_details_for_request(request) is True
    assert view.can_export_for_request(request) is True
