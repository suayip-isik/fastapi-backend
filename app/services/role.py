"""RoleService — rol ve permission yönetimi business logic."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.exceptions import AlreadyExistsError, BusinessRuleError, NotFoundError
from app.db.models.audit_log import AuditAction
from app.db.repositories.role import RoleRepository
from app.services._keys import USER_PERMISSIONS_KEY
from app.services.base import AuditableMixin
from app.services.cache import CacheService

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models.role import Role
    from app.services.audit import AuditService


class RoleService(AuditableMixin):
    """Rol yönetimi iş mantığı servisi.

    Rol CRUD işlemleri ve permission atamalarını yönetir.
    Sistem rolleri silinemez, adları değiştirilemez.
    """

    def __init__(self, session: AsyncSession, audit: AuditService | None = None) -> None:
        self._repo = RoleRepository(session)
        self._audit = audit

    async def list_roles(self) -> list[Role]:
        """Tüm rolleri alfabetik sırayla listeler."""
        return await self._repo.get_all_ordered()

    async def get_by_id(self, role_id: UUID) -> Role:
        """ID ile rol getirir.

        Raises:
            NotFoundError: Rol bulunamazsa.
        """
        role = await self._repo.get_by_id(role_id)
        if not role:
            raise NotFoundError("Rol bulunamadı.")
        return role

    async def get_by_name(self, name: str) -> Role:
        """İsim ile rol getirir.

        Raises:
            NotFoundError: Rol bulunamazsa.
        """
        role = await self._repo.get_by_name(name)
        if not role:
            raise NotFoundError(f"'{name}' adında bir rol bulunamadı.")
        return role

    async def create(
        self,
        name: str,
        description: str | None,
        permissions: list[str],
    ) -> Role:
        """Yeni özel rol oluşturur.

        Sistem rolleri bu metot ile oluşturulamaz (is_system=False).

        Raises:
            AlreadyExistsError: Aynı isimde rol mevcutsa.
        """
        if await self._repo.exists(name=name):
            raise AlreadyExistsError(f"'{name}' adında bir rol zaten mevcut.")
        role = await self._repo.create(name=name, description=description, is_system=False)
        if permissions:
            await self._repo.set_permissions(role.id, permissions)
            # Bulk DML identity map'i güncellemez; permissions koleksiyonunu tazele.
            await self._repo._session.refresh(role, attribute_names=["permissions"])
        await self._audit_log(
            AuditAction.ROLE_CREATED,
            extra={"role_name": name, "permissions": permissions},
        )
        return role

    async def update(
        self,
        role_id: UUID,
        description: str | None,
        permissions: list[str] | None,
    ) -> Role:
        """Rol açıklamasını ve/veya permission setini günceller.

        Sistem rollerinin açıklaması güncellenebilir ama permission
        seti değiştirilemez.

        Raises:
            NotFoundError: Rol bulunamazsa.
            BusinessRuleError: Sistem rolünün permissionları değiştirilmeye çalışılırsa.
        """
        role = await self.get_by_id(role_id)
        affected_user_ids: list[UUID] = []
        if permissions is not None and role.is_system:
            raise BusinessRuleError("Sistem rollerinin yetki seti değiştirilemez.")
        if description is not None:
            await self._repo.update(role_id, description=description)
        if permissions is not None:
            affected_user_ids = await self._repo.get_active_user_ids(role_id)
            await self._repo.set_permissions(role_id, permissions)
            await self._invalidate_permission_cache(affected_user_ids)
        await self._audit_log(
            AuditAction.ROLE_UPDATED,
            extra={
                "role_id": str(role_id),
                "role_name": role.name,
                "updated_description": description,
                "updated_permissions": permissions,
            },
        )
        # Cached role nesnesini expire et; get_by_id taze veri çeksin.
        self._repo._session.expire(role)
        return await self.get_by_id(role_id)

    async def _invalidate_permission_cache(self, user_ids: list[UUID]) -> None:
        """Role bağlı kullanıcıların permission cache'ini temizler."""
        if not user_ids:
            return
        await CacheService.delete(
            *(USER_PERMISSIONS_KEY.format(str(user_id)) for user_id in user_ids)
        )

    async def delete(self, role_id: UUID) -> None:
        """Özel rolü siler.

        Raises:
            NotFoundError: Rol bulunamazsa.
            BusinessRuleError: Sistem rolü silinmeye çalışılırsa.
            BusinessRuleError: Role atanmış aktif kullanıcı varsa.
        """
        role = await self.get_by_id(role_id)
        if role.is_system:
            raise BusinessRuleError("Sistem rolleri silinemez.")
        if await self._repo.has_users(role_id):
            raise BusinessRuleError(
                "Bu role atanmış kullanıcılar var. Önce kullanıcıların rolünü değiştirin."
            )
        await self._audit_log(
            AuditAction.ROLE_DELETED,
            extra={"role_id": str(role_id), "role_name": role.name},
        )
        await self._repo.soft_delete(role_id)
