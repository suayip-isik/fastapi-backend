"""
Audit log okuma servisi.

AuditService bağımsız session kullandığından (yazma için),
okuma işlemleri bu ayrı serviste tutulur.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.db.repositories.audit_log import AuditLogRepository

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models.audit_log import AuditAction, AuditLog


class AuditLogService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = AuditLogRepository(session)

    async def list_logs(
        self,
        *,
        user_id: UUID | None = None,
        action: AuditAction | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        ip_address: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[AuditLog], int]:
        offset = (page - 1) * size
        return await self._repo.get_filtered_page(
            user_id=user_id,
            action=action,
            date_from=date_from,
            date_to=date_to,
            ip_address=ip_address,
            offset=offset,
            limit=size,
        )

    async def get_log(self, log_id: UUID) -> AuditLog:
        return await self._repo.get_by_id_or_raise(log_id)
