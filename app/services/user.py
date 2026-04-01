"""
UserService — kullanıcı yönetimi business logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.exceptions import AlreadyExistsError, BusinessRuleError, UserNotFoundError
from app.core.security import hash_password
from app.db.models.audit_log import AuditAction
from app.db.repositories.user import UserRepository
from app.services._keys import USER_CACHE_KEY, USER_CACHE_TTL, USER_EMAIL_CACHE_KEY
from app.services.base import AuditableMixin
from app.services.cache import CacheService

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models.user import User, UserRole
    from app.schemas.user import UpdateUserRequest, UserResponse
    from app.services.audit import AuditService


class UserService(AuditableMixin):
    def __init__(self, session: AsyncSession, audit: AuditService | None = None) -> None:
        self._repo = UserRepository(session)
        self._audit = audit

    async def get_by_id(self, user_id: UUID) -> User:
        user = await self._repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError()
        return user

    async def get_by_id_cached(self, user_id: UUID) -> UserResponse:
        """Cache-aware accessor — sadece read-only display için."""
        from app.schemas.user import UserResponse as _UserResponse

        key = USER_CACHE_KEY.format(str(user_id))
        cached = await CacheService.get(key)
        if cached:
            return _UserResponse.model_validate(cached)
        user = await self._repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError()
        schema = _UserResponse.model_validate(user)
        await CacheService.set(key, schema.model_dump(), USER_CACHE_TTL)
        return schema

    async def _invalidate_user_cache(self, user_id: UUID, email: str | None = None) -> None:
        keys = [USER_CACHE_KEY.format(str(user_id))]
        if email:
            keys.append(USER_EMAIL_CACHE_KEY.format(email))
        await CacheService.delete(*keys)

    async def get_all(self, page: int = 1, size: int = 20) -> tuple[list[User], int]:
        return await self._repo.get_page(offset=(page - 1) * size, limit=size)

    async def update(self, user_id: UUID, data: UpdateUserRequest) -> User:
        user = await self._repo.get_by_id_or_raise(user_id)

        update_data = data.model_dump(exclude_unset=True)

        if (
            "email" in update_data
            and update_data["email"] != user.email
            and await self._repo.email_exists(update_data["email"])
        ):
            raise AlreadyExistsError("Bu e-posta adresi zaten kullanılıyor.")

        if "password" in update_data:
            update_data["hashed_password"] = hash_password(update_data.pop("password"))

        updated = await self._repo.update(user_id, **update_data)
        await self._audit_log(AuditAction.PROFILE_UPDATED, user_id=user_id)
        await self._invalidate_user_cache(user_id, updated.email)
        return updated

    async def deactivate(self, user_id: UUID) -> User:
        user = await self._repo.update(user_id, is_active=False)
        await self._audit_log(AuditAction.USER_DEACTIVATED, user_id=user_id)
        await self._invalidate_user_cache(user_id, user.email)
        return user

    async def activate(self, user_id: UUID) -> User:
        user = await self._repo.update(user_id, is_active=True)
        await self._audit_log(AuditAction.USER_ACTIVATED, user_id=user_id)
        await self._invalidate_user_cache(user_id, user.email)
        return user

    async def change_role(self, user_id: UUID, role: UserRole) -> User:
        current = await self._repo.get_by_id_or_raise(user_id)
        updated = await self._repo.update(user_id, role=role)
        await self._audit_log(
            AuditAction.ROLE_CHANGED,
            user_id=user_id,
            extra={"old_role": current.role.value, "new_role": role.value},
        )
        await self._invalidate_user_cache(user_id, updated.email)
        return updated

    async def soft_delete(self, user_id: UUID) -> None:
        user = await self._repo.get_by_id_or_raise(user_id)
        if user.is_deleted:
            raise BusinessRuleError("Kullanıcı zaten silinmiş.")
        await self._repo.soft_delete(user_id)
        await self._audit_log(AuditAction.USER_DELETED, user_id=user_id)
        await self._invalidate_user_cache(user_id, user.email)

    async def restore(self, user_id: UUID) -> User:
        user = await self._repo.get_by_id(user_id, include_deleted=True)
        if not user:
            raise UserNotFoundError()
        if not user.is_deleted:
            raise BusinessRuleError("Kullanıcı silinmemiş.")
        restored = await self._repo.restore(user_id)
        await self._audit_log(AuditAction.USER_RESTORED, user_id=user_id)
        await self._invalidate_user_cache(user_id, restored.email)
        return restored
