"""Notification repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select, update

from app.db.models.notification import Notification
from app.db.repositories.base import BaseRepository

if TYPE_CHECKING:
    from uuid import UUID


class NotificationRepository(BaseRepository[Notification]):
    model = Notification

    async def get_page_for_user(
        self,
        user_id: UUID,
        *,
        offset: int = 0,
        limit: int = 20,
        unread_first: bool = True,
    ) -> tuple[list[Notification], int]:
        """Kullanıcının bildirimlerini sayfalı döndür. Okunmamışlar önce gelir."""
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
        """Tüm okunmamış bildirimleri okundu işaretle. Etkilenen satır sayısını döndürür."""
        result = await self._session.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
            .values(is_read=True)
        )
        return result.rowcount

    async def count_unread(self, user_id: UUID) -> int:
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
