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

_MAX_PAGE_SIZE: int = 200

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

ModelType = TypeVar("ModelType", bound=BaseModel)
SoftDeleteModelType = TypeVar("SoftDeleteModelType", bound=SoftDeleteMixin)


class BaseRepository(Generic[ModelType], ABC):
    """Generic repository base sınıfı (CRUD operasyonları).

    Tüm repository'ler bu sınıftan türer. SQLAlchemy async session ile
    çalışır ve temel CRUD operasyonlarını sağlar. Soft-delete olmayan
    modeller için kullanılır.

    Type Parameters:
        ModelType: SQLAlchemy model tipi (BaseModel subclass)

    Attributes:
        model: SQLAlchemy model sınıfı (alt sınıfta tanımlanmalı)
        _session: AsyncSession database bağlantısı

    Example:
        >>> class AuditLogRepository(BaseRepository[AuditLog]):
        ...     model = AuditLog
        ...
        >>> repo = AuditLogRepository(session)
        >>> log = await repo.create(action="login", user_id=user_id)
    """

    model: type[ModelType]

    def __init__(self, session: AsyncSession) -> None:
        """Repository instance oluşturur.

        Args:
            session: SQLAlchemy AsyncSession database bağlantısı
        """
        self._session = session

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_by_id(self, id: UUID) -> ModelType | None:
        """ID ile kayıt getirir.

        Args:
            id: Kayıt UUID'si

        Returns:
            Model instance veya None (bulunamazsa)

        Example:
            >>> user = await repo.get_by_id(user_id)
            >>> if user:
            ...     print(user.email)
        """
        result = await self._session.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def get_by_id_or_raise(self, id: UUID) -> ModelType:
        """ID ile kayıt getirir, bulunamazsa hata fırlatır.

        Args:
            id: Kayıt UUID'si

        Returns:
            Model instance

        Raises:
            NotFoundError: Kayıt bulunamazsa

        Example:
            >>> user = await repo.get_by_id_or_raise(user_id)
            >>> print(user.email)  # Kesinlikle var
        """
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
        """Tüm kayıtları listeler (offset/limit ile).

        Args:
            offset: Atlanacak kayıt sayısı (default: 0)
            limit: Maksimum kayıt sayısı (default: 20)
            order_by: SQLAlchemy order_by ifadesi (ör: Model.created_at.desc())

        Returns:
            Model instance listesi

        Example:
            >>> users = await repo.get_all(offset=0, limit=10)
            >>> users = await repo.get_all(order_by=User.created_at.desc())
        """
        clamped_limit = min(limit, _MAX_PAGE_SIZE)
        query = select(self.model).offset(offset).limit(clamped_limit)
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
        """Sayfalanmış kayıtları ve toplam sayıyı getirir.

        Window function kullanarak tek sorguda hem kayıtları hem de
        toplam kayıt sayısını döndürür. Pagination için idealdir.

        Args:
            offset: Atlanacak kayıt sayısı (default: 0)
            limit: Sayfa başına kayıt sayısı (default: 20)

        Returns:
            (items, total_count) tuple - items liste, total toplam kayıt

        Example:
            >>> items, total = await repo.get_page(offset=0, limit=10)
            >>> print(f"Gösterilen: {len(items)}, Toplam: {total}")
        """
        clamped_limit = min(limit, _MAX_PAGE_SIZE)
        count_col = func.count().over().label("_total")
        stmt = select(self.model, count_col).offset(offset).limit(clamped_limit)
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
        """Cursor tabanlı keyset pagination.

        Offset pagination'a göre daha performanslıdır (büyük veri setleri için).
        (created_at, id) composite cursor kullanır ve limit+1 satır çekerek
        has_more tespiti yapar.

        Args:
            cursor: Önceki sayfanın son kaydının cursor değeri (ilk sayfa için None)
            limit: Sayfa başına kayıt sayısı (default: 20)
            order: Sıralama yönü - "asc" veya "desc" (default: "desc")

        Returns:
            (items, next_cursor) tuple - next_cursor=None ise son sayfa

        Example:
            >>> items, next_cursor = await repo.get_cursor_page(limit=10)
            >>> while next_cursor:
            ...     items, next_cursor = await repo.get_cursor_page(
            ...         cursor=next_cursor, limit=10
            ...     )
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
        """Toplam kayıt sayısını döndürür.

        Returns:
            Tablodaki toplam kayıt sayısı

        Example:
            >>> total = await repo.count()
            >>> print(f"Toplam kullanıcı: {total}")
        """
        result = await self._session.execute(select(func.count()).select_from(self.model))
        return result.scalar_one()

    async def exists(self, **filters: Any) -> bool:
        """Belirtilen filtrelere uyan kayıt var mı kontrol eder.

        Args:
            **filters: Field adı ve değer çiftleri (AND ile birleştirilir)

        Returns:
            True eğer en az bir kayıt varsa, False aksi halde

        Example:
            >>> exists = await repo.exists(email="test@example.com")
            >>> exists = await repo.exists(status="active", role="panel_admin")
        """
        query = select(func.count()).select_from(self.model)
        for key, value in filters.items():
            query = query.where(getattr(self.model, key) == value)
        result = await self._session.execute(query)
        return result.scalar_one() > 0

    # ── Write ─────────────────────────────────────────────────────────────────

    async def create(self, **data: Any) -> ModelType:
        """Yeni kayıt oluşturur.

        Model instance oluşturur, session'a ekler ve flush yapar.
        Flush sonrası ID üretilir ama commit henüz yapılmaz
        (transaction yönetimi üst katmana bırakılır).

        Args:
            **data: Model field değerleri

        Returns:
            Oluşturulan model instance (ID ile refresh edilmiş)

        Raises:
            IntegrityError: Unique constraint ihlali durumunda

        Example:
            >>> user = await repo.create(email="test@example.com", name="Test")
            >>> print(user.id)  # UUID atanmış
        """
        obj = self.model(**data)
        self._session.add(obj)
        await self._session.flush()
        await self._session.refresh(obj)
        return obj

    async def update(self, id: UUID, **data: Any) -> ModelType:
        """Kaydı günceller.

        Args:
            id: Güncellenecek kayıt UUID'si
            **data: Güncellenecek field değerleri

        Returns:
            Güncellenmiş model instance

        Raises:
            NotFoundError: Kayıt bulunamazsa

        Example:
            >>> user = await repo.update(user_id, name="Yeni İsim")
            >>> user = await repo.update(user_id, status="inactive", role="app_user")
        """
        await self._session.execute(update(self.model).where(self.model.id == id).values(**data))
        # populate_existing=True: bulk UPDATE sonrası identity map cache'ini es geçip
        # ilişkiler (selectin) dahil taze veri çeker.
        result = await self._session.execute(
            select(self.model).where(self.model.id == id).execution_options(populate_existing=True)
        )
        obj = result.scalar_one_or_none()
        if obj is None:
            from app.core.exceptions import NotFoundError

            raise NotFoundError(f"{self.model.__name__} bulunamadı: {id}")
        return obj

    async def delete(self, id: UUID) -> bool:
        """Kaydı kalıcı olarak siler (hard delete).

        Dikkat: Bu işlem geri alınamaz. Soft-delete için
        SoftDeleteRepository kullanın.

        Args:
            id: Silinecek kayıt UUID'si

        Returns:
            True silindi, False kayıt bulunamadı

        Example:
            >>> deleted = await repo.delete(user_id)
            >>> if deleted:
            ...     print("Kullanıcı silindi")
        """
        result = await self._session.execute(delete(self.model).where(self.model.id == id))
        return result.rowcount > 0

    async def bulk_create(self, items: list[dict[str, Any]]) -> list[ModelType]:
        """Toplu kayıt oluşturur.

        Birden fazla kaydı tek seferde oluşturur. Her kayıt için
        ayrı insert yapmaktan daha verimlidir.

        Args:
            items: Model field değerlerini içeren dict listesi

        Returns:
            Oluşturulan model instance listesi

        Example:
            >>> users = await repo.bulk_create([
            ...     {"email": "user1@example.com", "name": "User 1"},
            ...     {"email": "user2@example.com", "name": "User 2"},
            ... ])
        """
        objects = [self.model(**item) for item in items]
        self._session.add_all(objects)
        await self._session.flush()
        return objects


# ── SoftDeleteMixin'e sahip modeller için ─────────────────────────────────────

SoftModelType = TypeVar("SoftModelType", bound=BaseModel)


class SoftDeleteRepository(BaseRepository[SoftModelType]):
    """Soft-delete destekli generic repository.

    BaseRepository'nin tüm özelliklerini içerir ve soft-delete
    desteği ekler. Tüm read metodları varsayılan olarak
    deleted_at IS NULL filtresini uygular.

    Soft-delete, kaydı veritabanından silmek yerine deleted_at
    alanını doldurarak "silinmiş" olarak işaretler. Bu sayede
    veri kaybı olmaz ve gerektiğinde kayıt geri yüklenebilir.

    Type Parameters:
        SoftModelType: SoftDeleteMixin içeren SQLAlchemy model tipi

    Attributes:
        model: SQLAlchemy model sınıfı (alt sınıfta tanımlanmalı)
        _session: AsyncSession database bağlantısı

    Example:
        >>> class UserRepository(SoftDeleteRepository[User]):
        ...     model = User
        ...
        >>> repo = UserRepository(session)
        >>> await repo.soft_delete(user_id)  # deleted_at = now()
        >>> await repo.restore(user_id)      # deleted_at = NULL
    """

    async def get_by_id(self, id: UUID, *, include_deleted: bool = False) -> SoftModelType | None:
        """ID ile kayıt getirir.

        Varsayılan olarak silinmiş kayıtları hariç tutar.

        Args:
            id: Kayıt UUID'si
            include_deleted: True ise silinmiş kayıtları da dahil eder

        Returns:
            Model instance veya None (bulunamazsa)

        Example:
            >>> user = await repo.get_by_id(user_id)
            >>> deleted_user = await repo.get_by_id(user_id, include_deleted=True)
        """
        stmt = select(self.model).where(self.model.id == id)
        if not include_deleted:
            stmt = stmt.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_or_raise(self, id: UUID, *, include_deleted: bool = False) -> SoftModelType:
        """ID ile kayıt getirir, bulunamazsa hata fırlatır.

        Varsayılan olarak silinmiş kayıtları hariç tutar.

        Args:
            id: Kayıt UUID'si
            include_deleted: True ise silinmiş kayıtları da dahil eder

        Returns:
            Model instance

        Raises:
            NotFoundError: Kayıt bulunamazsa veya silinmişse (include_deleted=False)

        Example:
            >>> user = await repo.get_by_id_or_raise(user_id)
        """
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
        """Tüm kayıtları listeler (offset/limit ile).

        Varsayılan olarak silinmiş kayıtları hariç tutar.

        Args:
            offset: Atlanacak kayıt sayısı (default: 0)
            limit: Maksimum kayıt sayısı (default: 20)
            order_by: SQLAlchemy order_by ifadesi
            include_deleted: True ise silinmiş kayıtları da dahil eder

        Returns:
            Model instance listesi

        Example:
            >>> active_users = await repo.get_all(limit=10)
            >>> all_users = await repo.get_all(limit=10, include_deleted=True)
        """
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
        """Sayfalanmış kayıtları ve toplam sayıyı getirir.

        Window function kullanarak tek sorguda hem kayıtları hem de
        toplam kayıt sayısını döndürür. Varsayılan olarak silinmiş
        kayıtları hariç tutar.

        Args:
            offset: Atlanacak kayıt sayısı (default: 0)
            limit: Sayfa başına kayıt sayısı (default: 20)
            include_deleted: True ise silinmiş kayıtları da dahil eder

        Returns:
            (items, total_count) tuple - items liste, total toplam kayıt

        Example:
            >>> items, total = await repo.get_page(offset=0, limit=10)
        """
        count_col = func.count().over().label("_total")
        stmt = select(self.model, count_col)
        if not include_deleted:
            stmt = stmt.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        stmt = stmt.offset(offset).limit(limit)
        rows = (await self._session.execute(stmt)).all()
        items = [row[0] for row in rows]
        total = rows[0][1] if rows else 0
        return items, total

    async def exists(self, **filters: Any) -> bool:
        query = select(func.count()).select_from(self.model)
        query = query.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        for key, value in filters.items():
            query = query.where(getattr(self.model, key) == value)
        result = await self._session.execute(query)
        return result.scalar_one() > 0

    async def soft_delete(self, id: UUID) -> bool:
        """Kaydı soft-delete ile siler.

        Kaydı veritabanından silmez, deleted_at alanını şu anki
        zaman damgası ile doldurur. Daha sonra restore() ile
        geri yüklenebilir.

        Args:
            id: Silinecek kayıt UUID'si

        Returns:
            True işaretlendi, False kayıt bulunamadı

        Example:
            >>> deleted = await repo.soft_delete(user_id)
            >>> if deleted:
            ...     print("Kullanıcı soft-delete ile silindi")
        """
        result = await self._session.execute(
            update(self.model).where(self.model.id == id).values(deleted_at=datetime.now(UTC))
        )
        return result.rowcount > 0

    async def restore(self, id: UUID) -> SoftModelType:
        """Soft-delete ile silinmiş kaydı geri yükler.

        deleted_at alanını NULL yaparak kaydı aktif hale getirir.

        Args:
            id: Geri yüklenecek kayıt UUID'si

        Returns:
            Geri yüklenmiş model instance

        Raises:
            NotFoundError: Kayıt bulunamazsa

        Example:
            >>> user = await repo.restore(user_id)
            >>> print(f"{user.email} geri yüklendi")
        """
        await self._session.execute(
            update(self.model).where(self.model.id == id).values(deleted_at=None)
        )
        return await self.get_by_id_or_raise(id)
