"""Role repository — rol ve permission veritabanı işlemleri."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, exists, insert, select

if TYPE_CHECKING:
    from uuid import UUID

from app.core.exceptions import BusinessRuleError
from app.core.i18n import t
from app.core.permissions import find_invalid_permissions, normalize_permission_value
from app.db.models.role import Role, RolePermission
from app.db.models.user import User
from app.db.repositories.base import SoftDeleteRepository


class RoleRepository(SoftDeleteRepository[Role]):
    """Role modeli için repository.

    Rol CRUD işlemleri ve permission yönetimini sağlar.
    """

    model = Role

    def _validate_permissions(self, permissions: list[str]) -> list[str]:
        invalid_permissions = find_invalid_permissions(permissions)
        if invalid_permissions:
            raise BusinessRuleError(
                t("error.permissions.invalid", permissions=", ".join(sorted(invalid_permissions)))
            )
        return [normalize_permission_value(permission) for permission in permissions]

    async def get_by_name(self, name: str) -> Role | None:
        result = await self._session.execute(
            select(Role).where(Role.name == name, Role.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_all_ordered(self) -> list[Role]:
        result = await self._session.execute(
            select(Role).where(Role.deleted_at.is_(None)).order_by(Role.name)
        )
        return list(result.scalars().all())

    async def set_permissions(self, role_id: UUID, permissions: list[str]) -> None:
        """Rolün permission setini toptan günceller (sil + toplu ekle)."""
        normalized_permissions = self._validate_permissions(permissions)
        await self._session.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
        if normalized_permissions:
            await self._session.execute(
                insert(RolePermission),
                [{"role_id": role_id, "permission": p} for p in normalized_permissions],
            )
        await self._session.flush()

    async def add_permission(self, role_id: UUID, permission: str) -> None:
        """Mevcut permission setine tek bir permission ekler."""
        normalized_permission = self._validate_permissions([permission])[0]
        self._session.add(RolePermission(role_id=role_id, permission=normalized_permission))
        await self._session.flush()

    async def has_users(self, role_id: UUID) -> bool:
        """Bu role atanmış en az bir kullanıcı olup olmadığını döner."""
        result = await self._session.execute(
            select(exists().where(User.role_id == role_id, User.deleted_at.is_(None)))
        )
        return bool(result.scalar())

    async def get_active_user_ids(self, role_id: UUID) -> list[UUID]:
        """Role atanmış aktif kullanıcı ID'lerini döner."""
        result = await self._session.execute(
            select(User.id).where(User.role_id == role_id, User.deleted_at.is_(None))
        )
        return list(result.scalars().all())

    async def remove_permission(self, role_id: UUID, permission: str) -> None:
        """Mevcut permission setinden tek bir permission çıkarır."""
        normalized_permission = normalize_permission_value(permission)
        await self._session.execute(
            delete(RolePermission).where(
                RolePermission.role_id == role_id,
                RolePermission.permission == normalized_permission,
            )
        )
        await self._session.flush()
