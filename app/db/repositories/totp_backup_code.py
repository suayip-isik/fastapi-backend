"""TOTPBackupCodeRepository — backup kod CRUD işlemleri."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import delete, func, select, update

from app.db.models.totp_backup_code import TOTPBackupCode
from app.db.repositories.base import BaseRepository

if TYPE_CHECKING:
    from uuid import UUID


class TOTPBackupCodeRepository(BaseRepository[TOTPBackupCode]):
    model = TOTPBackupCode

    async def get_active_codes(self, user_id: UUID) -> list[TOTPBackupCode]:
        """Kullanıcının kullanılmamış backup kodlarını döndürür."""
        result = await self._session.execute(
            select(TOTPBackupCode).where(
                TOTPBackupCode.user_id == user_id,
                TOTPBackupCode.is_used.is_(False),
            )
        )
        return list(result.scalars().all())

    async def count_active(self, user_id: UUID) -> int:
        """Kullanılmamış backup kod sayısını döndürür."""
        result = await self._session.execute(
            select(func.count())
            .select_from(TOTPBackupCode)
            .where(
                TOTPBackupCode.user_id == user_id,
                TOTPBackupCode.is_used.is_(False),
            )
        )
        return result.scalar_one()

    async def mark_used(self, code_id: UUID) -> None:
        """Kodu kullanılmış olarak işaretle."""
        await self._session.execute(
            update(TOTPBackupCode)
            .where(TOTPBackupCode.id == code_id)
            .values(is_used=True, used_at=datetime.now(UTC))
        )

    async def delete_all_for_user(self, user_id: UUID) -> None:
        """Kullanıcının tüm backup kodlarını sil (regenerate veya disable öncesi)."""
        await self._session.execute(delete(TOTPBackupCode).where(TOTPBackupCode.user_id == user_id))
