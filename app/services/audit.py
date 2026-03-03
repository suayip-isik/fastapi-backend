"""
AuditService — kritik işlemleri DB'ye kaydeder.
Bağımsız session kullanır: ana işlem rollback yapsa bile audit yazılır.
"""

from __future__ import annotations

from uuid import UUID

from app.core.logging import get_logger, ip_address_var, user_agent_var
from app.db.models.audit_log import AuditAction
from app.db.repositories.audit_log import AuditLogRepository
from app.db.session import AsyncSessionFactory

_logger = get_logger(__name__)


class AuditService:
    async def log(
        self,
        action: AuditAction,
        user_id: UUID | None = None,
        extra: dict | None = None,
    ) -> None:
        ip = ip_address_var.get()
        ua = user_agent_var.get()
        async with AsyncSessionFactory() as session:
            try:
                await AuditLogRepository(session).create(
                    action=action,
                    user_id=user_id,
                    ip_address=ip if ip != "-" else None,
                    user_agent=ua if ua != "-" else None,
                    extra=extra,
                )
                await session.commit()
            except Exception as exc:
                await session.rollback()
                _logger.warning("audit_log_failed", action=action.value, exc=str(exc))
