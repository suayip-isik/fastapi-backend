"""
SQLAdmin view tanımları.
Her model için admin panelinde görünecek alanlar ve işlemler burada tanımlanır.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqladmin import ModelView

from app.core.permissions import Permission
from app.db.models.audit_log import AuditLog
from app.db.models.role import Role
from app.db.models.user import User


class PermissionScopedModelView(ModelView):
    """SQLAdmin view erişimini oturumdaki permission seti ile sınırlar."""

    required_permissions: tuple[str, ...] = ()

    @classmethod
    def _permission_values(cls, permissions: Iterable[Permission | str]) -> tuple[str, ...]:
        values: list[str] = []
        for permission in permissions:
            values.append(permission.value if isinstance(permission, Permission) else permission)
        return tuple(values)

    def _session_permissions(self, request: object) -> set[str]:
        session = getattr(request, "session", {})
        values = session.get("admin_permissions", [])
        if not isinstance(values, list):
            return set()
        return {str(value) for value in values}

    def is_accessible(self, request: object) -> bool:
        if not self.required_permissions:
            return True
        return bool(self._session_permissions(request) & set(self.required_permissions))

    def is_visible(self, request: object) -> bool:
        return self.is_accessible(request)


class UserAdmin(PermissionScopedModelView, model=User):
    """User modeli için SQLAdmin panel view."""

    required_permissions = PermissionScopedModelView._permission_values(
        (
            Permission.USERS_LIST,
            Permission.USERS_READ_BASIC,
            Permission.USERS_UPDATE_PROFILE,
            Permission.USERS_DELETE,
        )
    )

    name = "Kullanıcı"
    name_plural = "Kullanıcılar"
    icon = "fa-solid fa-users"

    column_list = [
        User.id,
        User.email,
        User.full_name,
        User.role,
        User.is_active,
        User.is_verified,
        User.created_at,
    ]

    column_searchable_list = [User.email, User.full_name, User.username]
    column_filters = [User.is_active, User.is_verified]
    column_sortable_list = [User.email, User.created_at]

    column_details_list = [
        User.id,
        User.email,
        User.username,
        User.full_name,
        User.avatar_url,
        User.role,
        User.is_active,
        User.is_verified,
        User.created_at,
        User.updated_at,
    ]

    form_columns = [
        User.email,
        User.username,
        User.full_name,
        User.role,
        User.is_active,
        User.is_verified,
    ]

    page_size = 25
    page_size_options = [25, 50, 100]

    can_create = True
    can_edit = True
    can_delete = True
    can_view_details = True
    can_export = True


class RoleAdmin(PermissionScopedModelView, model=Role):
    """Role modeli için SQLAdmin panel view.

    Rolleri ve permission setlerini görüntüler.
    Sistem rolleri silinmemelidir (is_system=True olanlar).
    """

    required_permissions = PermissionScopedModelView._permission_values(
        (
            Permission.ROLES_LIST,
            Permission.ROLES_READ_DETAIL,
            Permission.ROLES_UPDATE_DESCRIPTION,
            Permission.ROLES_UPDATE_PERMISSIONS,
            Permission.ROLES_DELETE,
        )
    )

    name = "Rol"
    name_plural = "Roller"
    icon = "fa-solid fa-shield"

    column_list = [
        Role.name,
        Role.description,
        Role.is_system,
        Role.created_at,
    ]

    column_searchable_list = [Role.name, Role.description]
    column_filters = [Role.is_system]
    column_sortable_list = [Role.name, Role.created_at]

    column_details_list = [
        Role.id,
        Role.name,
        Role.description,
        Role.is_system,
        Role.permissions,
        Role.created_at,
        Role.updated_at,
    ]

    form_columns = [Role.name, Role.description]

    page_size = 25
    page_size_options = [25, 50]

    can_create = True
    can_edit = True
    can_delete = True
    can_view_details = True
    can_export = True


class AuditLogAdmin(PermissionScopedModelView, model=AuditLog):
    """AuditLog modeli için SQLAdmin panel view — salt okunur."""

    required_permissions = PermissionScopedModelView._permission_values(
        (
            Permission.AUDIT_LOGS_LIST,
            Permission.AUDIT_LOGS_READ_DETAIL,
            Permission.AUDIT_LOGS_STREAM,
        )
    )

    name = "Audit Log"
    name_plural = "Audit Loglar"
    icon = "fa-solid fa-shield-halved"

    column_list = [
        AuditLog.created_at,
        AuditLog.action,
        AuditLog.user_id,
        AuditLog.ip_address,
        AuditLog.user_agent,
    ]

    column_searchable_list = [AuditLog.ip_address]
    column_filters = [AuditLog.action, AuditLog.user_id]
    column_sortable_list = [AuditLog.created_at, AuditLog.action]

    column_details_list = [
        AuditLog.id,
        AuditLog.created_at,
        AuditLog.action,
        AuditLog.user_id,
        AuditLog.ip_address,
        AuditLog.user_agent,
        AuditLog.extra,
    ]

    page_size = 50
    page_size_options = [50, 100, 200]

    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True
    can_export = True
