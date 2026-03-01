"""
User service — kullanıcı yönetimi business logic.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.core.security import hash_password
from app.db.models.user import User, UserRole
from app.db.repositories.user import UserRepository
from app.schemas.user import UpdateUserRequest


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = UserRepository(session)

    async def get_by_id(self, user_id: UUID) -> User:
        user = await self._repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("Kullanıcı bulunamadı.")
        return user

    async def get_all(self, page: int = 1, size: int = 20) -> tuple[list[User], int]:
        offset = (page - 1) * size
        users = await self._repo.get_all(offset=offset, limit=size)
        total = await self._repo.count()
        return users, total

    async def update(self, user_id: UUID, data: UpdateUserRequest) -> User:
        user = await self._repo.get_by_id_or_raise(user_id)

        update_data = data.model_dump(exclude_unset=True)

        if "email" in update_data and update_data["email"] != user.email:
            if await self._repo.email_exists(update_data["email"]):
                raise AlreadyExistsError("Bu e-posta adresi zaten kullanılıyor.")

        if "password" in update_data:
            update_data["hashed_password"] = hash_password(update_data.pop("password"))

        return await self._repo.update(user_id, **update_data)

    async def deactivate(self, user_id: UUID) -> User:
        return await self._repo.update(user_id, is_active=False)

    async def change_role(self, user_id: UUID, role: UserRole) -> User:
        return await self._repo.update(user_id, role=role)
