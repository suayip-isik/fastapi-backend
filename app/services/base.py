"""
Service katmanı için ortak base sınıflar.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.db.models.audit_log import AuditAction


class AuditableMixin:
    """Audit logging desteği ekleyen mixin sınıfı.

    Servisler bu mixin'i inherit ederek _audit_log() metoduna erişir.
    Kullanıcı aksiyonları otomatik olarak AuditLog tablosuna yazılır.

    Note:
        - AuditService inject edilmeli (constructor'da self._audit olarak)
        - _audit_log() async metot, await ile çağrılmalı

    Example:
        >>> class AuthService(AuditableMixin):
        ...     def __init__(self, audit_service: AuditService | None = None):
        ...         self._audit = audit_service
        ...
        ...     async def login(self, user: User, ip: str):
        ...         # Login logic...
        ...         await self._audit_log(
        ...             action=AuditAction.LOGIN,
        ...             user_id=user.id,
        ...             resource_type="user",
        ...             ip_address=ip
        ...         )
    """

    async def _audit_log(self, action: AuditAction, **kwargs: Any) -> None:
        """Audit log kaydı oluşturur.

        AuditService üzerinden log kaydı yapar. Service'de _audit attribute'u
        tanımlı değilse veya None ise sessizce atlar (fail-safe).

        Args:
            action: AuditAction enum değeri (LOGIN, LOGOUT, CREATE vb.)
            **kwargs: AuditService.log() metoduna iletilecek parametreler.
                Desteklenen parametreler:
                - user_id (UUID): Aksiyonu yapan kullanıcı ID
                - resource_type (str): İşlem yapılan kaynak tipi (user, api_key vb.)
                - resource_id (UUID | None): İşlem yapılan kaynak ID
                - details (dict | None): Ek JSON detaylar
                - ip_address (str | None): İstek yapan IP adresi
                - user_agent (str | None): Client user agent string

        Note:
            - _audit attribute None ise log kaydı atlanır (fail-safe)
            - details dict JSON serializable olmalı
        """
        audit = getattr(self, "_audit", None)
        if audit is not None:
            await audit.log(action, **kwargs)
