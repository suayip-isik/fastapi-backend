"""
Generic Repository Pattern.

Her entity için tekrar tekrar CRUD yazmak DRY'ı ihlal eder.
Bu base class, generic CRUD işlemlerini tek yerden sağlar.
Özel sorgular için alt class'ta override edilir.

Soft-delete gerektiren modeller için SoftDeleteRepository kullanın.
"""

from __future__ import annotations

from abc import ABC
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeVar

from sqlalchemy import and_, delete, func, or_, select, update

from app.db.models.base import BaseModel, SoftDeleteMixin

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

ModelType = TypeVar("ModelType", bound=BaseModel)
SoftDeleteModelType = TypeVar("SoftDeleteModelType", bound=SoftDeleteMixin)


class BaseRepository(Generic[ModelType], ABC):
    """
    Generic async repository — soft-delete olmayan modeller için.

    Kullanım:
        class AuditLogRepository(BaseRepository[AuditLog]):
            model = AuditLog
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

    async def get_cursor_page(
        self,
        *,
        cursor: str | None = None,
        limit: int = 20,
        order: Literal["asc", "desc"] = "desc",
    ) -> tuple[list[ModelType], str | None]:
        """
        Cursor tabanlı keyset pagination.

        (created_at, id) composite cursor kullanır.
        limit+1 satır çekerek has_more tespiti yapar.
        Döner: (items, next_cursor) — next_cursor=None ise son sayfa.
        """
        from app.schemas.common import decode_cursor, encode_cursor

        stmt = select(self.model)

        if cursor:
            cursor_ts, cursor_id = decode_cursor(cursor)
            if order == "desc":
                stmt = stmt.where(
                    or_(
                        self.model.created_at < cursor_ts,
                        and_(
                            self.model.created_at == cursor_ts,
                            self.model.id < cursor_id,
                        ),
                    )
                )
            else:
                stmt = stmt.where(
                    or_(
                        self.model.created_at > cursor_ts,
                        and_(
                            self.model.created_at == cursor_ts,
                            self.model.id > cursor_id,
                        ),
                    )
                )

        if order == "desc":
            stmt = stmt.order_by(self.model.created_at.desc(), self.model.id.desc())
        else:
            stmt = stmt.order_by(self.model.created_at.asc(), self.model.id.asc())

        stmt = stmt.limit(limit + 1)
        rows = list((await self._session.execute(stmt)).scalars().all())

        has_more = len(rows) > limit
        items = rows[:limit]
        next_cursor: str | None = None
        if has_more and items:
            last = items[-1]
            next_cursor = encode_cursor(last.created_at, last.id)

        return items, next_cursor

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


# ── SoftDeleteMixin'e sahip modeller için ─────────────────────────────────────

SoftModelType = TypeVar("SoftModelType", bound=BaseModel)


class SoftDeleteRepository(BaseRepository[SoftModelType]):
    """
    Soft-delete destekli repository.

    Tüm read metodları deleted_at IS NULL filtresini otomatik uygular.
    Soft-delete gerektiren modeller bu sınıfı kullanmalıdır.

    Kullanım:
        class UserRepository(SoftDeleteRepository[User]):
            model = User
    """

    async def get_by_id(self, id: UUID, *, include_deleted: bool = False) -> SoftModelType | None:
        stmt = select(self.model).where(self.model.id == id)
        if not include_deleted:
            stmt = stmt.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_or_raise(self, id: UUID, *, include_deleted: bool = False) -> SoftModelType:
        from app.core.exceptions import NotFoundError

        obj = await self.get_by_id(id, include_deleted=include_deleted)
        if not obj:
            raise NotFoundError(f"{self.model.__name__} bulunamadı: {id}")
        return obj

    async def get_all(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        order_by: Any = None,
        include_deleted: bool = False,
    ) -> list[SoftModelType]:
        stmt = select(self.model)
        if not include_deleted:
            stmt = stmt.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        stmt = stmt.offset(offset).limit(limit)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_page(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        include_deleted: bool = False,
    ) -> tuple[list[SoftModelType], int]:
        """Tek sorguda sayfa + toplam (window function). Silinmişleri hariç tutar."""
        count_col = func.count().over().label("_total")
        stmt = select(self.model, count_col)
        if not include_deleted:
            stmt = stmt.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        stmt = stmt.offset(offset).limit(limit)
        rows = (await self._session.execute(stmt)).all()
        items = [row[0] for row in rows]
        total = rows[0][1] if rows else 0
        return items, total

    async def soft_delete(self, id: UUID) -> bool:
        """deleted_at = now() olarak işaretle."""
        result = await self._session.execute(
            update(self.model).where(self.model.id == id).values(deleted_at=datetime.now(UTC))
        )
        return result.rowcount > 0

    async def restore(self, id: UUID) -> SoftModelType:
        """deleted_at = NULL yap ve güncel kaydı döndür."""
        await self._session.execute(
            update(self.model).where(self.model.id == id).values(deleted_at=None)
        )
        return await self.get_by_id_or_raise(id)
