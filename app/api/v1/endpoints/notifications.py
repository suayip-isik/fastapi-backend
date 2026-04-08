"""
Bildirim endpoint'leri.

GET    /notifications              → Sayfalı liste (okunmamış önce)
PATCH  /notifications/{id}        → Okundu işaretle
PATCH  /notifications/read-all    → Hepsini okundu işaretle
DELETE /notifications/{id}        → Sil
GET    /notifications/unread-count → Okunmamış sayısı
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUserDep
from app.api.dependencies.services import AuditServiceDep
from app.core.i18n import t
from app.db.session import get_db
from app.schemas.common import MessageResponse, PaginatedResponse, calculate_pages
from app.services.notification import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def get_notification_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    audit: AuditServiceDep,
) -> NotificationService:
    """NotificationService dependency factory'si."""
    return NotificationService(db, audit=audit)


NotificationServiceDep = Annotated[NotificationService, Depends(get_notification_service)]


# ── Schemas ───────────────────────────────────────────────────────────────────


class NotificationResponse(BaseModel):
    """NotificationResponse sınıfı."""

    id: UUID
    type: str
    title: str
    body: str | None
    data: dict[str, Any] | None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UnreadCountResponse(BaseModel):
    """UnreadCountResponse sınıfı."""

    count: int


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("", response_model=PaginatedResponse[NotificationResponse])
async def list_notifications(
    current_user: CurrentUserDep,
    service: NotificationServiceDep,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    unread_first: bool = Query(default=True),
) -> PaginatedResponse[NotificationResponse]:
    """Kullanıcının bildirimlerini sayfalı olarak listeler.

    Okunmamış bildirimleri önce gösterecek şekilde sıralanır.
    Sayfalama parametreleri ile sonuçlar filtrelenebilir.

    Args:
        current_user: Kimliği doğrulanmış mevcut kullanıcı.
        service: Bildirim işlemleri servisi.
        page: Sayfa numarası (varsayılan: 1).
        size: Sayfa başına bildirim sayısı (varsayılan: 20, maks: 100).
        unread_first: Okunmamışları önce göster (varsayılan: True).

    Returns:
        PaginatedResponse[NotificationResponse]: Sayfalanmış bildirim listesi.
    """
    items, total = await service.list_for_user(
        current_user.id, page=page, size=size, unread_first=unread_first
    )
    return PaginatedResponse(
        items=[NotificationResponse.model_validate(n) for n in items],
        total=total,
        page=page,
        size=size,
        pages=calculate_pages(total, size),
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count(
    current_user: CurrentUserDep,
    service: NotificationServiceDep,
) -> UnreadCountResponse:
    """Kullanıcının okunmamış bildirim sayısını döndürür.

    Bildirim rozeti veya sayacı göstermek için kullanılır.

    Args:
        current_user: Kimliği doğrulanmış mevcut kullanıcı.
        service: Bildirim işlemleri servisi.

    Returns:
        UnreadCountResponse: Okunmamış bildirim sayısını içeren yanıt.
    """
    count = await service.count_unread(current_user.id)
    return UnreadCountResponse(count=count)


@router.patch("/read-all", response_model=MessageResponse)
async def mark_all_read(
    current_user: CurrentUserDep,
    service: NotificationServiceDep,
) -> MessageResponse:
    """Kullanıcının tüm bildirimlerini okundu olarak işaretler.

    Toplu işlem olarak tüm okunmamış bildirimleri okundu durumuna geçirir.

    Args:
        current_user: Kimliği doğrulanmış mevcut kullanıcı.
        service: Bildirim işlemleri servisi.

    Returns:
        MessageResponse: İşaretlenen bildirim sayısını içeren mesaj.
    """
    count = await service.mark_all_read(current_user.id)
    return MessageResponse(message=t("notification.mark_all_read.success", count=count))


@router.patch("/{notification_id}", response_model=NotificationResponse)
async def mark_read(
    notification_id: UUID,
    current_user: CurrentUserDep,
    service: NotificationServiceDep,
) -> NotificationResponse:
    """Belirtilen bildirimi okundu olarak işaretler.

    Kullanıcı yalnızca kendi bildirimlerini işaretleyebilir.

    Args:
        notification_id: İşaretlenecek bildirimin UUID'si.
        current_user: Kimliği doğrulanmış mevcut kullanıcı.
        service: Bildirim işlemleri servisi.

    Returns:
        NotificationResponse: Güncellenen bildirimin detayları.

    Raises:
        HTTPException: Bildirim bulunamazsa 404 hatası döner.
    """
    notification = await service.mark_read(notification_id, current_user.id)
    return NotificationResponse.model_validate(notification)


@router.delete("/{notification_id}", response_model=MessageResponse)
async def delete_notification(
    notification_id: UUID,
    current_user: CurrentUserDep,
    service: NotificationServiceDep,
) -> MessageResponse:
    """Belirtilen bildirimi kalıcı olarak siler.

    Kullanıcı yalnızca kendi bildirimlerini silebilir.
    Bu işlem geri alınamaz.

    Args:
        notification_id: Silinecek bildirimin UUID'si.
        current_user: Kimliği doğrulanmış mevcut kullanıcı.
        service: Bildirim işlemleri servisi.

    Returns:
        MessageResponse: Silme işleminin başarılı olduğunu belirten mesaj.

    Raises:
        HTTPException: Bildirim bulunamazsa 404 hatası döner.
    """
    await service.delete(notification_id, current_user.id)
    return MessageResponse(message=t("notification.delete.success"))
