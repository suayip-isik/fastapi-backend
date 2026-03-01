"""User repository — domain-specific sorgular."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.user import User, UserRole
from app.db.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def get_with_oauth(self, user_id) -> User | None:
        """OAuth hesaplarıyla birlikte getir (eager load)."""
        result = await self._session.execute(
            select(User)
            .options(selectinload(User.oauth_accounts))
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_active_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.email == email.lower(), User.is_active == True)
        )
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        return await self.exists(email=email.lower())
