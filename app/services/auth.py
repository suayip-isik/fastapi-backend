"""
AuthService — email/password kimlik doğrulama ve token yönetimi.

Sorumluluklar: register · login · logout · refresh
OAuth akışları → OAuthService
Email doğrulama ve şifre sıfırlama → AccountService
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from app.core.exceptions import AuthenticationError, InvalidTokenError, UserAlreadyExistsError
from app.core.redis import get_redis_client
from app.core.security import (
    TokenType,
    create_token_pair,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.models.audit_log import AuditAction
from app.db.repositories.user import UserRepository
from app.schemas.auth import RegisterRequest, TokenResponse
from app.services._keys import BLACKLIST_KEY, EMAIL_VERIFY_KEY
from app.services.base import AuditableMixin
from app.tasks.worker import enqueue, send_verification_email

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models.user import User
    from app.services.audit import AuditService

_EMAIL_VERIFY_TTL = 24 * 60 * 60  # 24 saat


class AuthService(AuditableMixin):
    def __init__(self, session: AsyncSession, audit: AuditService | None = None) -> None:
        self._session = session
        self._repo = UserRepository(session)
        self._audit = audit

    async def register(self, data: RegisterRequest) -> User:
        if await self._repo.email_exists(data.email):
            raise UserAlreadyExistsError()

        user = await self._repo.create(
            email=data.email.lower(),
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
        )

        token = secrets.token_urlsafe(32)
        redis = await get_redis_client()
        await redis.setex(EMAIL_VERIFY_KEY.format(token), _EMAIL_VERIFY_TTL, str(user.id))
        await enqueue(send_verification_email, user.email, token)

        await self._audit_log(AuditAction.REGISTER, user_id=user.id)
        return user

    async def login(self, email: str, password: str, totp_code: str | None = None) -> TokenResponse:
        user = await self._repo.get_active_by_email(email)
        if not user or not user.hashed_password:
            await self._audit_log(AuditAction.LOGIN_FAILED, extra={"email": email})
            raise AuthenticationError("E-posta veya şifre hatalı.")

        if not verify_password(password, user.hashed_password):
            await self._audit_log(AuditAction.LOGIN_FAILED, user_id=user.id)
            raise AuthenticationError("E-posta veya şifre hatalı.")

        # 2FA kontrolü
        if user.totp_enabled:
            if not totp_code:
                raise AuthenticationError("Bu hesap için 2FA kodu gerekli.")
            from app.services.totp import TOTPService

            totp_svc = TOTPService(self._session)
            await totp_svc.check_login(user, totp_code)

        await self._audit_log(AuditAction.LOGIN_SUCCESS, user_id=user.id)
        tokens = create_token_pair(str(user.id))
        return TokenResponse(**tokens)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token)
        if payload.type != TokenType.REFRESH:
            raise InvalidTokenError("Geçersiz token türü.")

        redis = await get_redis_client()
        if await redis.exists(BLACKLIST_KEY.format(payload.jti)):
            raise InvalidTokenError("Refresh token geçersiz kılınmış.")

        user = await self._repo.get_by_id(UUID(payload.sub))
        if not user or not user.is_active:
            raise AuthenticationError("Kullanıcı bulunamadı.")

        # Eski refresh token'ı blacklist'e ekle (rotation)
        remaining = int((payload.exp - datetime.now(UTC)).total_seconds())
        if remaining > 0:
            await redis.setex(BLACKLIST_KEY.format(payload.jti), remaining, "1")

        await self._audit_log(AuditAction.TOKEN_REFRESHED, user_id=user.id)
        tokens = create_token_pair(str(user.id))
        return TokenResponse(**tokens)

    async def logout(
        self, access_token: str, refresh_token: str | None, user_id: UUID | None = None
    ) -> None:
        """Access ve refresh token'ları blacklist'e ekle."""
        redis = await get_redis_client()

        access_payload = decode_token(access_token)
        remaining = int((access_payload.exp - datetime.now(UTC)).total_seconds())
        if remaining > 0:
            await redis.setex(BLACKLIST_KEY.format(access_payload.jti), remaining, "1")

        if refresh_token:
            try:
                refresh_payload = decode_token(refresh_token)
                if refresh_payload.type == TokenType.REFRESH:
                    remaining = int((refresh_payload.exp - datetime.now(UTC)).total_seconds())
                    if remaining > 0:
                        await redis.setex(BLACKLIST_KEY.format(refresh_payload.jti), remaining, "1")
            except Exception:  # noqa: S110 - geçersiz refresh token logout'u engellememeli
                pass

        await self._audit_log(AuditAction.LOGOUT, user_id=user_id)
