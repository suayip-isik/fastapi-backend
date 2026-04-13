"""
SQLAdmin view tanımları.
Her model için admin panelinde görünecek alanlar ve işlemler burada tanımlanır.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqladmin import ModelView

from app.core.permissions import Permission
from app.db.models.audit_log import AuditLog
from app.db.models.role import Role
from app.db.models.user import User

if TYPE_CHECKING:
    from collections.abc import Iterable


class PermissionScopedModelView(ModelView):
    """SQLAdmin view erişimini oturumdaki permission seti ile sınırlar."""

    list_permissions: tuple[str, ...] = ()
    detail_permissions: tuple[str, ...] = ()
    create_permissions: tuple[str, ...] = ()
    edit_permissions: tuple[str, ...] = ()
    delete_permissions: tuple[str, ...] = ()
    export_permissions: tuple[str, ...] = ()

    list_permission_mode = "any"
    detail_permission_mode = "any"
    create_permission_mode = "any"
    edit_permission_mode = "all"
    delete_permission_mode = "any"
    export_permission_mode = "any"

    @classmethod
    def _permission_values(cls, permissions: Iterable[Permission | str]) -> tuple[str, ...]:
        return tuple(
            permission.value if isinstance(permission, Permission) else permission
            for permission in permissions
        )

    def _session_permissions(self, request: object) -> set[str]:
        session = getattr(request, "session", {})
        values = session.get("admin_permissions", [])
        if not isinstance(values, list):
            return set()
        return {str(value) for value in values}

    def _matches_permission_set(
        self, request: object, permissions: tuple[str, ...], mode: str
    ) -> bool:
        if not permissions:
            return True
        session_permissions = self._session_permissions(request)
        permission_set = set(permissions)
        if mode == "all":
            return permission_set.issubset(session_permissions)
        return bool(session_permissions & permission_set)

    def is_action_accessible(self, request: object, action: str) -> bool:
        if action == "list":
            return self._matches_permission_set(
                request, self.list_permissions, self.list_permission_mode
            )
        if action == "details":
            return self.can_view_details and self._matches_permission_set(
                request, self.detail_permissions, self.detail_permission_mode
            )
        if action == "create":
            return self.can_create and self._matches_permission_set(
                request, self.create_permissions, self.create_permission_mode
            )
        if action == "edit":
            return self.can_edit and self._matches_permission_set(
                request, self.edit_permissions, self.edit_permission_mode
            )
        if action == "delete":
            return self.can_delete and self._matches_permission_set(
                request, self.delete_permissions, self.delete_permission_mode
            )
        if action == "export":
            return self.can_export and self._matches_permission_set(
                request, self.export_permissions, self.export_permission_mode
            )
        return False

    def is_accessible(self, request: object) -> bool:
        return self.is_action_accessible(request, "list")

    def is_visible(self, request: object) -> bool:
        return self.is_accessible(request)

    def can_create_for_request(self, request: object) -> bool:
        return self.is_action_accessible(request, "create")

    def can_edit_for_request(self, request: object) -> bool:
        return self.is_action_accessible(request, "edit")

    def can_delete_for_request(self, request: object) -> bool:
        return self.is_action_accessible(request, "delete")

    def can_view_details_for_request(self, request: object) -> bool:
        return self.is_action_accessible(request, "details")

    def can_export_for_request(self, request: object) -> bool:
        return self.is_action_accessible(request, "export")


class UserAdmin(PermissionScopedModelView, model=User):
    """User modeli için SQLAdmin panel view."""

    list_permissions = PermissionScopedModelView._permission_values((Permission.USERS_LIST,))
    detail_permissions = PermissionScopedModelView._permission_values(
        (Permission.USERS_READ_BASIC,)
    )
    create_permissions = PermissionScopedModelView._permission_values(
        (Permission.USERS_CREATE_ADMIN,)
    )
    edit_permissions = PermissionScopedModelView._permission_values(
        (
            Permission.USERS_UPDATE_PROFILE,
            Permission.USERS_UPDATE_EMAIL,
            Permission.USERS_UPDATE_ROLE,
        )
    )
    delete_permissions = PermissionScopedModelView._permission_values((Permission.USERS_DELETE,))
    export_permissions = PermissionScopedModelView._permission_values((Permission.USERS_LIST,))

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

    list_permissions = PermissionScopedModelView._permission_values((Permission.ROLES_LIST,))
    detail_permissions = PermissionScopedModelView._permission_values(
        (Permission.ROLES_READ_DETAIL,)
    )
    create_permissions = PermissionScopedModelView._permission_values((Permission.ROLES_CREATE,))
    edit_permissions = PermissionScopedModelView._permission_values(
        (Permission.ROLES_UPDATE_DESCRIPTION,)
    )
    delete_permissions = PermissionScopedModelView._permission_values((Permission.ROLES_DELETE,))
    export_permissions = PermissionScopedModelView._permission_values((Permission.ROLES_LIST,))

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

    form_columns = [Role.description]

    page_size = 25
    page_size_options = [25, 50]

    can_create = True
    can_edit = True
    can_delete = True
    can_view_details = True
    can_export = True


class AuditLogAdmin(PermissionScopedModelView, model=AuditLog):
    """AuditLog modeli için SQLAdmin panel view — salt okunur."""

    list_permissions = PermissionScopedModelView._permission_values((Permission.AUDIT_LOGS_LIST,))
    detail_permissions = PermissionScopedModelView._permission_values(
        (Permission.AUDIT_LOGS_READ_DETAIL,)
    )
    export_permissions = PermissionScopedModelView._permission_values(
        (Permission.AUDIT_LOGS_STREAM,)
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
