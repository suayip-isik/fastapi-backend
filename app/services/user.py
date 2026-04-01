"""
UserService — kullanıcı yönetimi business logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.core.security import hash_password
from app.db.models.audit_log import AuditAction
from app.db.repositories.user import UserRepository
from app.services.base import AuditableMixin

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models.user import User, UserRole
    from app.schemas.user import UpdateUserRequest
    from app.services.audit import AuditService


class UserService(AuditableMixin):
    def __init__(self, session: AsyncSession, audit: AuditService | None = None) -> None:
        self._repo = UserRepository(session)
        self._audit = audit

    async def get_by_id(self, user_id: UUID) -> User:
        user = await self._repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("Kullanıcı bulunamadı.")
        return user

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
        return updated

    async def deactivate(self, user_id: UUID) -> User:
        user = await self._repo.update(user_id, is_active=False)
        await self._audit_log(AuditAction.USER_DEACTIVATED, user_id=user_id)
        return user

    async def activate(self, user_id: UUID) -> User:
        user = await self._repo.update(user_id, is_active=True)
        await self._audit_log(AuditAction.USER_ACTIVATED, user_id=user_id)
        return user

    async def change_role(self, user_id: UUID, role: UserRole) -> User:
        current = await self._repo.get_by_id_or_raise(user_id)
        updated = await self._repo.update(user_id, role=role)
        await self._audit_log(
            AuditAction.ROLE_CHANGED,
            user_id=user_id,
            extra={"old_role": current.role.value, "new_role": role.value},
        )
        return updated
