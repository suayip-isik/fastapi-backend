"""
Audit log endpoint'leri — sadece admin erişimi.

GET /audit-logs          → Sayfalı liste (filtreli)
GET /audit-logs/{log_id} → Tek log detayı
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import AdminDep
from app.db.models.audit_log import AuditAction
from app.db.session import get_db
from app.schemas.common import CursorPaginatedResponse, PaginatedResponse, calculate_pages
from app.services.audit_log import AuditLogService

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


def get_audit_log_service(db: Annotated[AsyncSession, Depends(get_db)]) -> AuditLogService:
    """AuditLogService dependency factory'si."""
    return AuditLogService(db)


AuditLogServiceDep = Annotated[AuditLogService, Depends(get_audit_log_service)]


# ── Schemas ───────────────────────────────────────────────────────────────────


class AuditLogResponse(BaseModel):
    """AuditLogResponse sınıfı."""

    id: UUID
    user_id: UUID | None
    action: str
    ip_address: str | None
    user_agent: str | None
    extra: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("", response_model=PaginatedResponse[AuditLogResponse])
async def list_audit_logs(
    _: AdminDep,
    service: AuditLogServiceDep,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    user_id: UUID | None = Query(default=None),
    action: AuditAction | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    ip_address: str | None = Query(default=None),
) -> PaginatedResponse[AuditLogResponse]:
    """Audit log kayıtlarını sayfalı ve filtreli olarak listeler.

    Sistemdeki tüm audit log kayıtlarını offset-based pagination ile döndürür.
    Kullanıcı, aksiyon türü, tarih aralığı ve IP adresi gibi kriterlere göre
    filtreleme yapılabilir.

    Args:
        _: Mevcut admin kullanıcı (yetki kontrolü için).
        service: Audit log işlemlerini yöneten servis.
        page: Sayfa numarası (1'den başlar).
        size: Sayfa başına kayıt sayısı (1-100 arası).
        user_id: Belirli bir kullanıcıya ait logları filtreler.
        action: Belirli bir aksiyon türüne göre filtreler.
        date_from: Bu tarihten sonraki logları getirir.
        date_to: Bu tarihten önceki logları getirir.
        ip_address: Belirli bir IP adresine göre filtreler.

    Returns:
        PaginatedResponse[AuditLogResponse]: Sayfalanmış audit log listesi.
            items, total, page, size ve pages alanlarını içerir.

    Raises:
        HTTPException (403): Kullanıcı admin değilse.
    """
    items, total = await service.list_logs(
        user_id=user_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
        ip_address=ip_address,
        page=page,
        size=size,
    )
    return PaginatedResponse(
        items=[AuditLogResponse.model_validate(log) for log in items],
        total=total,
        page=page,
        size=size,
        pages=calculate_pages(total, size),
    )


@router.get("/stream", response_model=CursorPaginatedResponse[AuditLogResponse])
async def stream_audit_logs(
    _: AdminDep,
    service: AuditLogServiceDep,
    cursor: str | None = Query(default=None, description="Sayfalama cursor'ı"),
    size: int = Query(default=20, ge=1, le=100),
    user_id: UUID | None = Query(default=None),
    action: AuditAction | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    ip_address: str | None = Query(default=None),
) -> CursorPaginatedResponse[AuditLogResponse]:
    """Cursor tabanlı pagination ile audit loglarını akış olarak getirir.

    Büyük veri setleri için optimize edilmiş cursor-based pagination kullanır.
    Offset-based pagination'a göre daha performanslıdır çünkü veritabanı
    önceki kayıtları atlamak zorunda kalmaz.

    Args:
        _: Mevcut admin kullanıcı (yetki kontrolü için).
        service: Audit log işlemlerini yöneten servis.
        cursor: Bir önceki yanıttaki next_cursor değeri. İlk istek için None.
        size: Sayfa başına kayıt sayısı (1-100 arası).
        user_id: Belirli bir kullanıcıya ait logları filtreler.
        action: Belirli bir aksiyon türüne göre filtreler.
        date_from: Bu tarihten sonraki logları getirir.
        date_to: Bu tarihten önceki logları getirir.
        ip_address: Belirli bir IP adresine göre filtreler.

    Returns:
        CursorPaginatedResponse[AuditLogResponse]: Cursor ile sayfalanmış yanıt.
            items, next_cursor, has_more ve size alanlarını içerir.
            Sonraki sayfa için next_cursor değerini cursor parametresi olarak gönderin.

    Raises:
        HTTPException (403): Kullanıcı admin değilse.
    """
    items, next_cursor = await service.list_logs_cursor(
        user_id=user_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
        ip_address=ip_address,
        cursor=cursor,
        size=size,
    )
    return CursorPaginatedResponse(
        items=[AuditLogResponse.model_validate(log) for log in items],
        next_cursor=next_cursor,
        has_more=next_cursor is not None,
        size=len(items),
    )


@router.get("/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    log_id: UUID,
    _: AdminDep,
    service: AuditLogServiceDep,
) -> AuditLogResponse:
    """Belirtilen ID'ye sahip audit log kaydının detaylarını getirir.

    Tek bir audit log kaydının tüm bilgilerini (kullanıcı, aksiyon, IP adresi,
    user agent ve ek veriler dahil) döndürür.

    Args:
        log_id: Getirilecek audit log kaydının UUID'si.
        _: Mevcut admin kullanıcı (yetki kontrolü için).
        service: Audit log işlemlerini yöneten servis.

    Returns:
        AuditLogResponse: Audit log kaydının detaylı bilgileri.

    Raises:
        HTTPException (403): Kullanıcı admin değilse.
        HTTPException (404): Belirtilen ID'ye sahip log bulunamazsa.
    """
    log = await service.get_log(log_id)
    return AuditLogResponse.model_validate(log)
