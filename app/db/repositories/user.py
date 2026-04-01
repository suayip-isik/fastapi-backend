"""User repository — domain-specific sorgular."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.db.models.user import User
from app.db.repositories.base import SoftDeleteRepository

if TYPE_CHECKING:
    from uuid import UUID


class UserRepository(SoftDeleteRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.email == email.lower(), User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.username == username, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_with_oauth(self, user_id: UUID) -> User | None:
        """OAuth hesaplariyla birlikte getir (eager load)."""
        result = await self._session.execute(
            select(User)
            .options(selectinload(User.oauth_accounts))
            .where(User.id == user_id, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_active_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(User).where(
                User.email == email.lower(),
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        result = await self._session.execute(
            select(func.count())
            .select_from(User)
            .where(User.email == email.lower(), User.deleted_at.is_(None))
        )
        return result.scalar_one() > 0

    async def get_deleted_page(self, *, offset: int = 0, limit: int = 20) -> tuple[list[User], int]:
        """Sadece soft-deleted kullanıcıları döndürür (admin trash view)."""
        count_col = func.count().over().label("_total")
        stmt = (
            select(User, count_col).where(User.deleted_at.is_not(None)).offset(offset).limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        items = [row[0] for row in rows]
        total = rows[0][1] if rows else 0
        return items, total
