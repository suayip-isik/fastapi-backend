"""
Service katmanı için ortak base sınıflar.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.db.models.audit_log import AuditAction

if TYPE_CHECKING:
    from app.services.audit import AuditService


class AuditableMixin:
    """
    Audit log yazma yeteneği katan mixin.

    Kullanan service __init__ içinde self._audit atamalı:
        self._audit: AuditService | None = audit
    """

    async def _audit_log(self, action: AuditAction, **kwargs) -> None:
        audit = getattr(self, "_audit", None)
        if audit is not None:
            await audit.log(action, **kwargs)
