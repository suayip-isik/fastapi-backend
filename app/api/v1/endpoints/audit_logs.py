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
from app.schemas.common import PaginatedResponse
from app.services.audit_log import AuditLogService

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


def get_audit_log_service(db: Annotated[AsyncSession, Depends(get_db)]) -> AuditLogService:
    return AuditLogService(db)


AuditLogServiceDep = Annotated[AuditLogService, Depends(get_audit_log_service)]


# ── Schemas ───────────────────────────────────────────────────────────────────


class AuditLogResponse(BaseModel):
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
    """Audit logları sayfalı ve filtreli listele. Sadece admin."""
    items, total = await service.list_logs(
        user_id=user_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
        ip_address=ip_address,
        page=page,
        size=size,
    )
    pages = (total + size - 1) // size if total > 0 else 0
    return PaginatedResponse(
        items=[AuditLogResponse.model_validate(log) for log in items],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get("/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    log_id: UUID,
    _: AdminDep,
    service: AuditLogServiceDep,
) -> AuditLogResponse:
    """Tek audit log kaydını getir. Sadece admin."""
    log = await service.get_log(log_id)
    return AuditLogResponse.model_validate(log)
