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
from app.db.session import get_db
from app.schemas.common import MessageResponse, PaginatedResponse
from app.services.notification import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def get_notification_service(db: Annotated[AsyncSession, Depends(get_db)]) -> NotificationService:
    return NotificationService(db)


NotificationServiceDep = Annotated[NotificationService, Depends(get_notification_service)]


# ── Schemas ───────────────────────────────────────────────────────────────────


class NotificationResponse(BaseModel):
    id: UUID
    type: str
    title: str
    body: str | None
    data: dict[str, Any] | None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UnreadCountResponse(BaseModel):
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
    """Bildirimleri sayfalı listele."""
    items, total = await service.list_for_user(
        current_user.id, page=page, size=size, unread_first=unread_first
    )
    pages = (total + size - 1) // size if total > 0 else 0
    return PaginatedResponse(
        items=[NotificationResponse.model_validate(n) for n in items],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count(
    current_user: CurrentUserDep,
    service: NotificationServiceDep,
) -> UnreadCountResponse:
    """Okunmamış bildirim sayısını döndür."""
    count = await service.count_unread(current_user.id)
    return UnreadCountResponse(count=count)


@router.patch("/read-all", response_model=MessageResponse)
async def mark_all_read(
    current_user: CurrentUserDep,
    service: NotificationServiceDep,
) -> MessageResponse:
    """Tüm bildirimleri okundu olarak işaretle."""
    count = await service.mark_all_read(current_user.id)
    return MessageResponse(message=f"{count} bildirim okundu olarak işaretlendi.")


@router.patch("/{notification_id}", response_model=NotificationResponse)
async def mark_read(
    notification_id: UUID,
    current_user: CurrentUserDep,
    service: NotificationServiceDep,
) -> NotificationResponse:
    """Bildirimi okundu olarak işaretle."""
    notification = await service.mark_read(notification_id, current_user.id)
    return NotificationResponse.model_validate(notification)


@router.delete("/{notification_id}", response_model=MessageResponse)
async def delete_notification(
    notification_id: UUID,
    current_user: CurrentUserDep,
    service: NotificationServiceDep,
) -> MessageResponse:
    """Bildirimi sil."""
    await service.delete(notification_id, current_user.id)
    return MessageResponse(message="Bildirim silindi.")
