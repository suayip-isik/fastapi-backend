"""
AuditService — kritik işlemleri DB'ye kaydeder.
Bağımsız session kullanır: ana işlem rollback yapsa bile audit yazılır.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger, ip_address_var, user_agent_var
from app.db.repositories.audit_log import AuditLogRepository
from app.db.session import AsyncSessionFactory

if TYPE_CHECKING:
    from uuid import UUID

    from app.db.models.audit_log import AuditAction

_logger = get_logger(__name__)


class AuditService:
    """Kritik işlemlerin audit loglarını yöneten servis.

    Bu servis bağımsız veritabanı session'ı kullanır. Ana işlem
    rollback yapsa bile audit kaydı başarıyla yazılır.
    """

    async def log(
        self,
        action: AuditAction,
        user_id: UUID | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Audit log kaydı oluşturur.

        Belirtilen aksiyonu, kullanıcı bilgilerini ve ek verileri
        veritabanına kaydeder. IP adresi ve user agent otomatik
        olarak context variable'lardan alınır.

        Args:
            action: Kaydedilecek audit aksiyonu (örn: LOGIN, LOGOUT).
            user_id: İşlemi yapan kullanıcının UUID'si. Anonim
                işlemler için None olabilir.
            extra: Aksiyona özgü ek veriler. JSON olarak saklanır.

        Note:
            Kayıt başarısız olursa hata fırlatılmaz, sadece log yazılır.
            Bu, ana iş akışının audit hatası nedeniyle kesilmemesini sağlar.
        """
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
