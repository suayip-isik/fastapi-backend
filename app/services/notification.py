"""
NotificationService — bildirim oluşturma, listeleme ve yönetimi.

WebSocket entegrasyonu: Bildirim oluşturulduğunda bağlı kullanıcıya anlık iletilir.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.db.models.audit_log import AuditAction
from app.db.models.notification import Notification, NotificationType
from app.db.repositories.notification import NotificationRepository
from app.services.base import AuditableMixin

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.audit import AuditService

logger = get_logger(__name__)


class NotificationService(AuditableMixin):
    """Bildirim olusturma/listeleme ve durum guncelleme servisidir."""

    def __init__(self, session: AsyncSession, audit: AuditService | None = None) -> None:
        self._repo = NotificationRepository(session)
        self._audit = audit

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
        """Yeni bildirim oluşturur ve isteğe bağlı olarak WebSocket üzerinden iletir.

        Args:
            user_id: Bildirimin gönderileceği kullanıcının UUID'si.
            title: Bildirim başlığı.
            type: Bildirim türü. Varsayılan INFO.
            body: Bildirim içeriği (opsiyonel).
            data: Ek JSON verisi (opsiyonel).
            push_via_ws: True ise bildirim WebSocket üzerinden anında iletilir.

        Returns:
            Oluşturulan Notification nesnesi.
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
        """Bağlı kullanıcıya WebSocket mesajı gönderir.

        Bağlantı yoksa veya hata oluşursa sessizce başarısız olur ve log kaydı tutar.

        Args:
            notification: Gönderilecek bildirim nesnesi.
        """
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
        """Kullanıcının bildirimlerini sayfalı olarak listeler.

        Args:
            user_id: Bildirimleri listelenecek kullanıcının UUID'si.
            page: Sayfa numarası (1'den başlar).
            size: Sayfa başına bildirim sayısı.
            unread_first: True ise okunmamış bildirimler önce gösterilir.

        Returns:
            (bildirim_listesi, toplam_sayı) tuple'ı.
        """
        offset = (page - 1) * size
        return await self._repo.get_page_for_user(
            user_id, offset=offset, limit=size, unread_first=unread_first
        )

    async def mark_read(self, notification_id: UUID, user_id: UUID) -> Notification:
        """Belirtilen bildirimi okundu olarak işaretler.

        Args:
            notification_id: İşaretlenecek bildirimin UUID'si.
            user_id: İşlemi yapan kullanıcının UUID'si (yetki kontrolü için).

        Returns:
            Güncellenen Notification nesnesi.

        Raises:
            NotFoundError: Bildirim bulunamazsa veya kullanıcıya ait değilse.
        """
        notification = await self._repo.get_by_id(notification_id)
        if not notification or notification.user_id != user_id:
            raise NotFoundError("Bildirim bulunamadı.")
        result = await self._repo.update(notification_id, is_read=True)
        await self._audit_log(
            AuditAction.NOTIFICATION_READ,
            user_id=user_id,
            extra={"notification_id": str(notification_id)},
        )
        return result

    async def mark_all_read(self, user_id: UUID) -> int:
        """Kullanıcının tüm bildirimlerini okundu olarak işaretler.

        Args:
            user_id: Bildirimleri işaretlenecek kullanıcının UUID'si.

        Returns:
            Güncellenen bildirim sayısı.
        """
        return await self._repo.mark_all_read(user_id)

    async def delete(self, notification_id: UUID, user_id: UUID) -> None:
        """Belirtilen bildirimi siler.

        Args:
            notification_id: Silinecek bildirimin UUID'si.
            user_id: İşlemi yapan kullanıcının UUID'si (yetki kontrolü için).

        Raises:
            NotFoundError: Bildirim bulunamazsa veya kullanıcıya ait değilse.
        """
        notification = await self._repo.get_by_id(notification_id)
        if not notification or notification.user_id != user_id:
            raise NotFoundError("Bildirim bulunamadı.")
        await self._repo.delete(notification_id)
        await self._audit_log(
            AuditAction.NOTIFICATION_DELETED,
            user_id=user_id,
            extra={"notification_id": str(notification_id)},
        )

    async def count_unread(self, user_id: UUID) -> int:
        """Kullanıcının okunmamış bildirim sayısını döndürür.

        Args:
            user_id: Sayılacak kullanıcının UUID'si.

        Returns:
            Okunmamış bildirim sayısı.
        """
        return await self._repo.count_unread(user_id)
