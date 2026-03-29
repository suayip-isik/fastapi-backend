"""
AccountService — email doğrulama ve şifre sıfırlama işlemleri.

Sorumluluklar: verify_email · resend_verification · forgot_password · reset_password
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING
from uuid import UUID

from app.core.exceptions import InvalidTokenError
from app.core.redis import get_redis_client
from app.core.security import hash_password
from app.db.models.audit_log import AuditAction
from app.db.repositories.user import UserRepository
from app.services._keys import EMAIL_VERIFY_KEY, PASSWORD_RESET_KEY
from app.services.base import AuditableMixin
from app.tasks.worker import enqueue, send_password_reset_email, send_verification_email

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.audit import AuditService

_EMAIL_VERIFY_TTL = 24 * 60 * 60  # 24 saat
_PASSWORD_RESET_TTL = 15 * 60  # 15 dakika


class AccountService(AuditableMixin):
    def __init__(self, session: AsyncSession, audit: AuditService | None = None) -> None:
        self._repo = UserRepository(session)
        self._audit = audit

    # ── Email Verification ────────────────────────────────────────────────────

    async def verify_email(self, token: str) -> None:
        """Token geçerliyse kullanıcıyı doğrulanmış olarak işaretle."""
        redis = await get_redis_client()
        user_id = await redis.get(EMAIL_VERIFY_KEY.format(token))
        if not user_id:
            raise InvalidTokenError("Geçersiz veya süresi dolmuş doğrulama token'ı.")

        await redis.delete(EMAIL_VERIFY_KEY.format(token))

        user = await self._repo.get_by_id(UUID(user_id))
        if not user:
            raise InvalidTokenError("Kullanıcı bulunamadı.")

        if not user.is_verified:
            await self._repo.update(user.id, is_verified=True)

        await self._audit_log(AuditAction.EMAIL_VERIFIED, user_id=user.id)

    async def resend_verification(self, email: str) -> None:
        """Doğrulama e-postasını yeniden gönder. Kullanıcı yoksa sessizce döner."""
        user = await self._repo.get_active_by_email(email)
        if not user or user.is_verified:
            return

        token = secrets.token_urlsafe(32)
        redis = await get_redis_client()
        await redis.setex(EMAIL_VERIFY_KEY.format(token), _EMAIL_VERIFY_TTL, str(user.id))
        await enqueue(send_verification_email, user.email, token)

    # ── Password Reset ────────────────────────────────────────────────────────

    async def forgot_password(self, email: str) -> None:
        """Şifre sıfırlama e-postası gönder. Kullanıcı yoksa sessizce döner."""
        user = await self._repo.get_active_by_email(email)
        if not user or not user.hashed_password:
            return  # OAuth kullanıcısı ya da var olmayan e-posta — user enumeration yok

        token = secrets.token_urlsafe(32)
        redis = await get_redis_client()
        await redis.setex(PASSWORD_RESET_KEY.format(token), _PASSWORD_RESET_TTL, str(user.id))
        await enqueue(send_password_reset_email, user.email, token)

        await self._audit_log(AuditAction.PASSWORD_RESET_REQUESTED, user_id=user.id)

    async def reset_password(self, token: str, new_password: str) -> None:
        """Token geçerliyse şifreyi güncelle."""
        redis = await get_redis_client()
        user_id = await redis.get(PASSWORD_RESET_KEY.format(token))
        if not user_id:
            raise InvalidTokenError("Geçersiz veya süresi dolmuş şifre sıfırlama token'ı.")

        await redis.delete(PASSWORD_RESET_KEY.format(token))

        user = await self._repo.get_by_id(UUID(user_id))
        if not user or not user.is_active:
            raise InvalidTokenError("Kullanıcı bulunamadı.")

        await self._repo.update(user.id, hashed_password=hash_password(new_password))
        await self._audit_log(AuditAction.PASSWORD_RESET, user_id=user.id)
