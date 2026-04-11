"""Bildirim repository modülü.

Bu modül, bildirim verilerine erişim için repository sınıfını içerir.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select, update

from app.db.models.notification import Notification
from app.db.repositories.base import BaseRepository

if TYPE_CHECKING:
    from uuid import UUID


class NotificationRepository(BaseRepository[Notification]):
    """Bildirim veritabanı işlemleri için repository sınıfı.

    Bu sınıf, kullanıcı bildirimlerinin CRUD işlemlerini ve
    özel sorgularını yönetir. BaseRepository'den miras alarak
    temel CRUD operasyonlarını sağlar.

    Attributes:
        model: Notification SQLAlchemy modeli.
    """

    model = Notification

    async def get_page_for_user(
        self,
        user_id: UUID,
        *,
        offset: int = 0,
        limit: int = 20,
        unread_first: bool = True,
    ) -> tuple[list[Notification], int]:
        """Kullanıcının bildirimlerini sayfalanmış olarak getirir.

        Belirtilen kullanıcıya ait bildirimleri sayfalama desteğiyle döndürür.
        Varsayılan olarak okunmamış bildirimler listenin başında yer alır.

        Args:
            user_id: Bildirimleri getirilecek kullanıcının UUID'si.
            offset: Atlanacak kayıt sayısı. Varsayılan 0.
            limit: Döndürülecek maksimum kayıt sayısı. Varsayılan 20.
            unread_first: True ise okunmamış bildirimler önce gelir.
                Varsayılan True.

        Returns:
            İki elemanlı tuple:
                - Bildirim listesi (Notification nesneleri).
                - Toplam bildirim sayısı (sayfalama için).
        """
        from sqlalchemy import func

        count_col = func.count().over().label("_total")
        if unread_first:
            stmt = (
                select(Notification, count_col)
                .where(Notification.user_id == user_id)
                .order_by(Notification.is_read.asc(), Notification.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        else:
            stmt = (
                select(Notification, count_col)
                .where(Notification.user_id == user_id)
                .order_by(Notification.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        rows = (await self._session.execute(stmt)).all()
        items = [row[0] for row in rows]
        total = rows[0][1] if rows else 0
        return items, total

    async def mark_all_read(self, user_id: UUID) -> int:
        """Kullanıcının tüm okunmamış bildirimlerini okundu olarak işaretler.

        Args:
            user_id: Bildirimleri güncellenecek kullanıcının UUID'si.

        Returns:
            Güncellenen (okundu işaretlenen) bildirim sayısı.
        """
        result = await self._session.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
            .values(is_read=True)
        )
        return result.rowcount

    async def count_unread(self, user_id: UUID) -> int:
        """Kullanıcının okunmamış bildirim sayısını döndürür.

        Args:
            user_id: Okunmamış bildirimleri sayılacak kullanıcının UUID'si.

        Returns:
            Okunmamış bildirim sayısı.
        """
        from sqlalchemy import func

        result = await self._session.execute(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
        )
        return result.scalar_one()
