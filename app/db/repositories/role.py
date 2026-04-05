"""Role repository — rol ve permission veritabanı işlemleri."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, exists, select

if TYPE_CHECKING:
    from uuid import UUID

from app.db.models.role import Role, RolePermission
from app.db.models.user import User
from app.db.repositories.base import SoftDeleteRepository


class RoleRepository(SoftDeleteRepository[Role]):
    """Role modeli için repository.

    Rol CRUD işlemleri ve permission yönetimini sağlar.
    """

    model = Role

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
        """Rolün permission setini toptan günceller (sil + ekle)."""
        await self._session.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
        for perm in permissions:
            self._session.add(RolePermission(role_id=role_id, permission=perm))
        await self._session.flush()

    async def add_permission(self, role_id: UUID, permission: str) -> None:
        """Mevcut permission setine tek bir permission ekler."""
        self._session.add(RolePermission(role_id=role_id, permission=permission))
        await self._session.flush()

    async def has_users(self, role_id: UUID) -> bool:
        """Bu role atanmış en az bir kullanıcı olup olmadığını döner."""
        result = await self._session.execute(
            select(exists().where(User.role_id == role_id, User.deleted_at.is_(None)))
        )
        return result.scalar()

    async def remove_permission(self, role_id: UUID, permission: str) -> None:
        """Mevcut permission setinden tek bir permission çıkarır."""
        await self._session.execute(
            delete(RolePermission).where(
                RolePermission.role_id == role_id,
                RolePermission.permission == permission,
            )
        )
        await self._session.flush()
