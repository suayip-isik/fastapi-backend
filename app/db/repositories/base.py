"""
Generic Repository Pattern.

Her entity için tekrar tekrar CRUD yazmak DRY'ı ihlal eder.
Bu base class, generic CRUD işlemlerini tek yerden sağlar.
Özel sorgular için alt class'ta override edilir.
"""

from __future__ import annotations

from abc import ABC
from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType], ABC):
    """
    Generic async repository.

    Kullanım:
        class UserRepository(BaseRepository[User]):
            model = User
    """

    model: type[ModelType]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_by_id(self, id: UUID) -> ModelType | None:
        result = await self._session.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def get_by_id_or_raise(self, id: UUID) -> ModelType:
        from app.core.exceptions import NotFoundError

        obj = await self.get_by_id(id)
        if not obj:
            raise NotFoundError(f"{self.model.__name__} bulunamadı: {id}")
        return obj

    async def get_all(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        order_by: Any = None,
    ) -> list[ModelType]:
        query = select(self.model).offset(offset).limit(limit)
        if order_by is not None:
            query = query.order_by(order_by)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_page(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[ModelType], int]:
        """Tek sorguda sayfa + toplam kayıt sayısı (window function)."""
        count_col = func.count().over().label("_total")
        stmt = select(self.model, count_col).offset(offset).limit(limit)
        rows = (await self._session.execute(stmt)).all()
        items = [row[0] for row in rows]
        total = rows[0][1] if rows else 0
        return items, total

    async def count(self) -> int:
        result = await self._session.execute(select(func.count()).select_from(self.model))
        return result.scalar_one()

    async def exists(self, **filters: Any) -> bool:
        query = select(func.count()).select_from(self.model)
        for key, value in filters.items():
            query = query.where(getattr(self.model, key) == value)
        result = await self._session.execute(query)
        return result.scalar_one() > 0

    # ── Write ─────────────────────────────────────────────────────────────────

    async def create(self, **data: Any) -> ModelType:
        obj = self.model(**data)
        self._session.add(obj)
        await self._session.flush()  # ID üretilsin, commit henüz yapılmasın
        await self._session.refresh(obj)
        return obj

    async def update(self, id: UUID, **data: Any) -> ModelType:
        await self._session.execute(update(self.model).where(self.model.id == id).values(**data))
        return await self.get_by_id_or_raise(id)

    async def delete(self, id: UUID) -> bool:
        result = await self._session.execute(delete(self.model).where(self.model.id == id))
        return result.rowcount > 0

    async def bulk_create(self, items: list[dict[str, Any]]) -> list[ModelType]:
        objects = [self.model(**item) for item in items]
        self._session.add_all(objects)
        await self._session.flush()
        return objects
