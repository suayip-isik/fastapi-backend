"""
Auth service — tüm kimlik doğrulama business logic'i burada.
Route handler'lar sadece bu service'i çağırır.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AlreadyExistsError, AuthenticationError, InvalidTokenError
from app.core.redis import get_redis_client
from app.core.security import (
    TokenType,
    create_token_pair,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.models.user import User
from app.db.repositories.user import UserRepository
from app.schemas.auth import RegisterRequest, TokenResponse
from app.tasks.worker import enqueue, send_verification_email, send_password_reset_email

_EMAIL_VERIFY_TTL = 24 * 60 * 60  # 24 saat (saniye)
_PASSWORD_RESET_TTL = 15 * 60  # 15 dakika (saniye)


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = UserRepository(session)

    # ── Email/Password ────────────────────────────────────────────────────────

    async def register(self, data: RegisterRequest) -> User:
        if await self._repo.email_exists(data.email):
            raise AlreadyExistsError("Bu e-posta adresi zaten kullanılıyor.")

        user = await self._repo.create(
            email=data.email.lower(),
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
        )

        token = secrets.token_urlsafe(32)
        redis = await get_redis_client()
        await redis.setex(f"email_verify:{token}", _EMAIL_VERIFY_TTL, str(user.id))
        await enqueue(send_verification_email, user.email, token)

        return user

    async def login(self, email: str, password: str) -> TokenResponse:
        user = await self._repo.get_active_by_email(email)
        if not user or not user.hashed_password:
            raise AuthenticationError("E-posta veya şifre hatalı.")

        if not verify_password(password, user.hashed_password):
            raise AuthenticationError("E-posta veya şifre hatalı.")

        tokens = create_token_pair(str(user.id))
        return TokenResponse(**tokens)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token)
        if payload.type != TokenType.REFRESH:
            raise InvalidTokenError("Geçersiz token türü.")

        redis = await get_redis_client()
        if await redis.exists(f"blacklist:{payload.jti}"):
            raise InvalidTokenError("Refresh token geçersiz kılınmış.")

        user = await self._repo.get_by_id(payload.sub)
        if not user or not user.is_active:
            raise AuthenticationError("Kullanıcı bulunamadı.")

        # Eski refresh token'ı blacklist'e ekle (rotation)
        remaining = int((payload.exp - datetime.now(timezone.utc)).total_seconds())
        if remaining > 0:
            await redis.setex(f"blacklist:{payload.jti}", remaining, "1")

        tokens = create_token_pair(str(user.id))
        return TokenResponse(**tokens)

    async def logout(self, access_token: str, refresh_token: str | None) -> None:
        """Access ve refresh token'ları blacklist'e ekle."""
        redis = await get_redis_client()

        access_payload = decode_token(access_token)
        remaining = int((access_payload.exp - datetime.now(timezone.utc)).total_seconds())
        if remaining > 0:
            await redis.setex(f"blacklist:{access_payload.jti}", remaining, "1")

        if refresh_token:
            try:
                refresh_payload = decode_token(refresh_token)
                if refresh_payload.type == TokenType.REFRESH:
                    remaining = int(
                        (refresh_payload.exp - datetime.now(timezone.utc)).total_seconds()
                    )
                    if remaining > 0:
                        await redis.setex(f"blacklist:{refresh_payload.jti}", remaining, "1")
            except Exception:
                pass  # Geçersiz refresh token — sessizce geç

    # ── Google OAuth ──────────────────────────────────────────────────────────

    def get_google_auth_url(self) -> str:
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"https://accounts.google.com/o/oauth2/auth?{query}"

    async def google_callback(self, code: str) -> TokenResponse:
        # 1. Code → access token
        async with httpx.AsyncClient() as client:
            token_res = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )
            token_res.raise_for_status()
            token_data = token_res.json()

            # 2. Token → user info
            userinfo_res = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {token_data['access_token']}"},
            )
            userinfo_res.raise_for_status()
            userinfo = userinfo_res.json()

        return await self._upsert_oauth_user(
            provider="google",
            provider_user_id=userinfo["sub"],
            email=userinfo["email"],
            full_name=userinfo.get("name"),
            avatar_url=userinfo.get("picture"),
            access_token=token_data.get("access_token"),
        )

    # ── GitHub OAuth ──────────────────────────────────────────────────────────

    def get_github_auth_url(self) -> str:
        return (
            f"https://github.com/login/oauth/authorize"
            f"?client_id={settings.GITHUB_CLIENT_ID}"
            f"&redirect_uri={settings.GITHUB_REDIRECT_URI}"
            f"&scope=user:email"
        )

    async def github_callback(self, code: str) -> TokenResponse:
        async with httpx.AsyncClient() as client:
            token_res = await client.post(
                "https://github.com/login/oauth/access_token",
                json={
                    "client_id": settings.GITHUB_CLIENT_ID,
                    "client_secret": settings.GITHUB_CLIENT_SECRET,
                    "code": code,
                },
                headers={"Accept": "application/json"},
            )
            token_res.raise_for_status()
            access_token = token_res.json()["access_token"]

            user_res = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            user_res.raise_for_status()
            gh_user = user_res.json()

            email_res = await client.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            emails = email_res.json()
            primary_email = next(
                (e["email"] for e in emails if e.get("primary")),
                gh_user.get("email"),
            )

        return await self._upsert_oauth_user(
            provider="github",
            provider_user_id=str(gh_user["id"]),
            email=primary_email,
            full_name=gh_user.get("name"),
            avatar_url=gh_user.get("avatar_url"),
            access_token=access_token,
        )

    # ── Email Verification ────────────────────────────────────────────────────

    async def verify_email(self, token: str) -> None:
        """Token geçerliyse kullanıcıyı doğrulanmış olarak işaretle."""
        redis = await get_redis_client()
        user_id = await redis.get(f"email_verify:{token}")
        if not user_id:
            raise InvalidTokenError("Geçersiz veya süresi dolmuş doğrulama token'ı.")

        await redis.delete(f"email_verify:{token}")

        user = await self._repo.get_by_id(user_id)
        if not user:
            raise InvalidTokenError("Kullanıcı bulunamadı.")

        if not user.is_verified:
            await self._repo.update(user.id, is_verified=True)

    async def resend_verification(self, email: str) -> None:
        """Doğrulama e-postasını yeniden gönder. Kullanıcı yoksa sessizce döner."""
        user = await self._repo.get_active_by_email(email)
        if not user or user.is_verified:
            return

        token = secrets.token_urlsafe(32)
        redis = await get_redis_client()
        await redis.setex(f"email_verify:{token}", _EMAIL_VERIFY_TTL, str(user.id))
        await enqueue(send_verification_email, user.email, token)

    # ── Password Reset ────────────────────────────────────────────────────────

    async def forgot_password(self, email: str) -> None:
        """Şifre sıfırlama e-postası gönder. Kullanıcı yoksa sessizce döner."""
        user = await self._repo.get_active_by_email(email)
        if not user or not user.hashed_password:
            return  # OAuth kullanıcısı ya da var olmayan e-posta — user enumeration yok

        token = secrets.token_urlsafe(32)
        redis = await get_redis_client()
        await redis.setex(f"password_reset:{token}", _PASSWORD_RESET_TTL, str(user.id))
        await enqueue(send_password_reset_email, user.email, token)

    async def reset_password(self, token: str, new_password: str) -> None:
        """Token geçerliyse şifreyi güncelle."""
        redis = await get_redis_client()
        user_id = await redis.get(f"password_reset:{token}")
        if not user_id:
            raise InvalidTokenError("Geçersiz veya süresi dolmuş şifre sıfırlama token'ı.")

        await redis.delete(f"password_reset:{token}")

        user = await self._repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise InvalidTokenError("Kullanıcı bulunamadı.")

        await self._repo.update(user.id, hashed_password=hash_password(new_password))

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _upsert_oauth_user(
        self,
        *,
        provider: str,
        provider_user_id: str,
        email: str,
        full_name: str | None,
        avatar_url: str | None,
        access_token: str | None,
    ) -> TokenResponse:
        """OAuth kullanıcısını bul ya da oluştur."""
        user = await self._repo.get_active_by_email(email)

        if not user:
            user = await self._repo.create(
                email=email.lower(),
                full_name=full_name,
                avatar_url=avatar_url,
                is_verified=True,  # OAuth ile gelen e-posta doğrulanmış sayılır
            )

        tokens = create_token_pair(str(user.id))
        return TokenResponse(**tokens)
