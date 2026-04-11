"""AuditLog repository.

Bu modül, denetim günlüğü (audit log) kayıtlarına erişim için
repository sınıfını içerir.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, func, or_, select

from app.db.models.audit_log import AuditAction, AuditLog
from app.db.repositories.base import BaseRepository

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID


class AuditLogRepository(BaseRepository[AuditLog]):
    """Denetim günlüğü kayıtları için repository sınıfı.

    Bu sınıf, AuditLog modeli üzerinde CRUD işlemleri ve özelleştirilmiş
    sorgular sağlar. BaseRepository'den miras alır ve filtreleme,
    sayfalama gibi ek özellikler sunar.

    Attributes:
        model: Bu repository'nin çalıştığı SQLAlchemy model sınıfı.

    Example:
        >>> repo = AuditLogRepository(session)
        >>> logs, total = await repo.get_filtered_page(user_id=user.id)
    """

    model = AuditLog

    def _apply_filters(
        self,
        stmt: Any,
        *,
        user_id: UUID | None,
        action: AuditAction | None,
        date_from: datetime | None,
        date_to: datetime | None,
        ip_address: str | None,
    ) -> Any:
        """Ortak filtre koşullarını SQL ifadesine uygular.

        Verilen parametrelere göre WHERE koşullarını dinamik olarak ekler.
        None olan parametreler filtrelemeye dahil edilmez.

        Args:
            stmt: Filtrelerin uygulanacağı SQLAlchemy select ifadesi.
            user_id: Filtrelenecek kullanıcı UUID'si.
            action: Filtrelenecek denetim eylemi türü.
            date_from: Başlangıç tarihi (dahil).
            date_to: Bitiş tarihi (dahil).
            ip_address: Filtrelenecek IP adresi.

        Returns:
            Filtreler uygulanmış SQLAlchemy select ifadesi.
        """
        if user_id is not None:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if action is not None:
            stmt = stmt.where(AuditLog.action == action)
        if date_from is not None:
            stmt = stmt.where(AuditLog.created_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(AuditLog.created_at <= date_to)
        if ip_address is not None:
            stmt = stmt.where(AuditLog.ip_address == ip_address)
        return stmt

    async def get_filtered_page(
        self,
        *,
        user_id: UUID | None = None,
        action: AuditAction | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        ip_address: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[AuditLog], int]:
        """Filtreli ve sayfalı denetim günlüğü sorgusu yapar.

        Window function kullanarak tek sorguda hem sonuçları hem de
        toplam kayıt sayısını döndürür. Sonuçlar oluşturulma tarihine
        göre azalan sırada sıralanır.

        Args:
            user_id: Filtrelenecek kullanıcı UUID'si.
            action: Filtrelenecek denetim eylemi türü.
            date_from: Başlangıç tarihi (dahil).
            date_to: Bitiş tarihi (dahil).
            ip_address: Filtrelenecek IP adresi.
            offset: Atlanacak kayıt sayısı (sayfalama için).
            limit: Döndürülecek maksimum kayıt sayısı.

        Returns:
            İki elemanlı tuple:
                - Denetim günlüğü kayıtlarının listesi.
                - Filtrelere uyan toplam kayıt sayısı.

        Example:
            >>> logs, total = await repo.get_filtered_page(
            ...     action=AuditAction.LOGIN,
            ...     limit=10
            ... )
        """
        count_col = func.count().over().label("_total")
        stmt = select(AuditLog, count_col).order_by(AuditLog.created_at.desc())
        stmt = self._apply_filters(
            stmt,
            user_id=user_id,
            action=action,
            date_from=date_from,
            date_to=date_to,
            ip_address=ip_address,
        )
        stmt = stmt.offset(offset).limit(limit)
        rows = (await self._session.execute(stmt)).all()
        items = [row[0] for row in rows]
        total = rows[0][1] if rows else 0
        return items, total

    async def get_cursor_filtered_page(
        self,
        *,
        user_id: UUID | None = None,
        action: AuditAction | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        ip_address: str | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> tuple[list[AuditLog], str | None]:
        """Filtreli cursor tabanlı denetim günlüğü sorgusu yapar.

        Offset yerine cursor kullanarak daha verimli sayfalama sağlar.
        Büyük veri setlerinde offset-based sayfalamaya göre daha performanslıdır.
        Cursor, created_at ve id alanlarının kombinasyonundan oluşur.

        Args:
            user_id: Filtrelenecek kullanıcı UUID'si.
            action: Filtrelenecek denetim eylemi türü.
            date_from: Başlangıç tarihi (dahil).
            date_to: Bitiş tarihi (dahil).
            ip_address: Filtrelenecek IP adresi.
            cursor: Önceki sayfanın son kaydını temsil eden cursor değeri.
                None ise ilk sayfadan başlar.
            limit: Döndürülecek maksimum kayıt sayısı.

        Returns:
            İki elemanlı tuple:
                - Denetim günlüğü kayıtlarının listesi.
                - Sonraki sayfa için cursor değeri. Daha fazla kayıt yoksa None.

        Example:
            >>> # İlk sayfa
            >>> logs, next_cursor = await repo.get_cursor_filtered_page(limit=20)
            >>> # Sonraki sayfa
            >>> logs, next_cursor = await repo.get_cursor_filtered_page(
            ...     cursor=next_cursor,
            ...     limit=20
            ... )
        """
        from app.schemas.common import decode_cursor, encode_cursor

        stmt = select(AuditLog)
        stmt = self._apply_filters(
            stmt,
            user_id=user_id,
            action=action,
            date_from=date_from,
            date_to=date_to,
            ip_address=ip_address,
        )

        if cursor:
            cursor_ts, cursor_id = decode_cursor(cursor)
            stmt = stmt.where(
                or_(
                    AuditLog.created_at < cursor_ts,
                    and_(
                        AuditLog.created_at == cursor_ts,
                        AuditLog.id < cursor_id,
                    ),
                )
            )

        stmt = stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        stmt = stmt.limit(limit + 1)

        rows = list((await self._session.execute(stmt)).scalars().all())
        has_more = len(rows) > limit
        items = rows[:limit]
        next_cursor: str | None = None
        if has_more and items:
            last = items[-1]
            next_cursor = encode_cursor(last.created_at, last.id)

        return items, next_cursor
