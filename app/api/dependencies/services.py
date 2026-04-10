"""
Merkezi servis dependency'leri.
Endpoint dosyalarında tekrarlanan servis bağımlılıkları burada tanımlanır.
"""

from typing import Annotated

from fastapi import Depends

from app.db.session_provider import get_default_session_factory
from app.services.audit import AuditService


def get_audit_service() -> AuditService:
    """AuditService instance döner (dependency injection).

    AuditService bağımsız session provider üzerinden çalıştığından herhangi
    bir request-scope DB dependency'sine ihtiyaç duymaz. FastAPI dependency
    injection sistemi tarafından otomatik çözümlenir.

    Returns:
        AuditService: Audit log yazma işlemleri için servis instance'ı.

    Note:
        AuditService, servis katmanındaki işlem rollback'lerinden bağımsız
        kendi oturumunu yönetir; bu nedenle request transaction'ından etkilenmez.

    Example:
        >>> @router.post("/users")
        >>> async def create_user(
        ...     data: CreateUserRequest,
        ...     audit: AuditServiceDep,
        ... ) -> UserResponse:
        ...     return await user_service.create(data, audit=audit)
    """
    return AuditService(session_factory=get_default_session_factory())


AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]
"""Audit log servisi dependency type alias.

Endpoint parametrelerinde `audit: AuditServiceDep` şeklinde kullanılır.
AuditService, servis katmanına audit log yazmak için iletilir.

Note:
    AuditService bağımsız session provider kullandığından istek transaction'ından
    etkilenmez; rollback olsa bile audit kaydı yazılır.

Example:
    >>> @router.delete("/users/{user_id}")
    >>> async def delete_user(
    ...     user_id: UUID,
    ...     _: Annotated[User, Depends(require_permissions(Permission.USERS_DELETE))],
    ...     audit: AuditServiceDep,
    ... ) -> None:
    ...     await user_service.delete(user_id, audit=audit)
"""
