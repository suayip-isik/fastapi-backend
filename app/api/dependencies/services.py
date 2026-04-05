"""
Merkezi servis dependency'leri.
Endpoint dosyalarında tekrarlanan servis bağımlılıkları burada tanımlanır.
"""

from typing import Annotated

from fastapi import Depends

from app.services.audit import AuditService


def get_audit_service() -> AuditService:
    """AuditService instance döner (dependency injection).

    AuditService bağımsız bir AsyncSessionFactory oturumu kullandığından
    herhangi bir parametre gerektirmez. FastAPI dependency injection sistemi
    tarafından otomatik çözümlenir.

    Returns:
        AuditService: Audit log yazma işlemleri için servis instance'ı.

    Note:
        AuditService, servis katmanındaki işlem rollback'lerinden bağımsız
        kendi oturumunu yönetir; bu nedenle DB session dependency'sine
        ihtiyaç duymaz.

    Example:
        >>> @router.post("/users")
        >>> async def create_user(
        ...     data: CreateUserRequest,
        ...     audit: AuditServiceDep,
        ... ) -> UserResponse:
        ...     return await user_service.create(data, audit=audit)
    """
    return AuditService()


AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]
"""Audit log servisi dependency type alias.

Endpoint parametrelerinde `audit: AuditServiceDep` şeklinde kullanılır.
AuditService, servis katmanına audit log yazmak için iletilir.

Note:
    AuditService bağımsız oturum kullandığından istek transaction'ından
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
