"""
NotificationService — bildirim oluşturma, listeleme ve yönetimi.

WebSocket entegrasyonu: Bildirim oluşturulduğunda bağlı kullanıcıya anlık iletilir.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.db.models.notification import Notification, NotificationType
from app.db.repositories.notification import NotificationRepository

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class NotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = NotificationRepository(session)

    async def create(
        self,
        user_id: UUID,
        title: str,
        *,
        type: NotificationType = NotificationType.INFO,
        body: str | None = None,
        data: dict[str, Any] | None = None,
        push_via_ws: bool = True,
    ) -> Notification:
        """
        Yeni bildirim oluştur ve isteğe bağlı olarak WebSocket üzerinden ilet.
        """
        notification = await self._repo.create(
            user_id=user_id,
            type=type,
            title=title,
            body=body,
            data=data,
        )

        if push_via_ws:
            await self._push_to_websocket(notification)

        return notification

    async def _push_to_websocket(self, notification: Notification) -> None:
        """Bağlı kullanıcıya WebSocket mesajı gönder. Sessizce başarısız olur."""
        try:
            from app.websockets.manager import manager

            payload: dict[str, object] = {
                "type": "notification",
                "id": str(notification.id),
                "notification_type": notification.type.value,
                "title": notification.title,
                "body": notification.body,
                "data": notification.data,
                "created_at": notification.created_at.isoformat(),
            }
            await manager.send_to_user_all_rooms(str(notification.user_id), payload)
        except Exception as e:
            logger.warning("ws_notification_push_failed", error=str(e))

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        page: int = 1,
        size: int = 20,
        unread_first: bool = True,
    ) -> tuple[list[Notification], int]:
        offset = (page - 1) * size
        return await self._repo.get_page_for_user(
            user_id, offset=offset, limit=size, unread_first=unread_first
        )

    async def mark_read(self, notification_id: UUID, user_id: UUID) -> Notification:
        notification = await self._repo.get_by_id(notification_id)
        if not notification or notification.user_id != user_id:
            raise NotFoundError("Bildirim bulunamadı.")
        return await self._repo.update(notification_id, is_read=True)

    async def mark_all_read(self, user_id: UUID) -> int:
        return await self._repo.mark_all_read(user_id)

    async def delete(self, notification_id: UUID, user_id: UUID) -> None:
        notification = await self._repo.get_by_id(notification_id)
        if not notification or notification.user_id != user_id:
            raise NotFoundError("Bildirim bulunamadı.")
        await self._repo.delete(notification_id)

    async def count_unread(self, user_id: UUID) -> int:
        return await self._repo.count_unread(user_id)
