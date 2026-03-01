"""
Auth service — tüm kimlik doğrulama business logic'i burada.
Route handler'lar sadece bu service'i çağırır.
"""
from __future__ import annotations

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AlreadyExistsError, AuthenticationError, InvalidTokenError
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


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = UserRepository(session)

    # ── Email/Password ────────────────────────────────────────────────────────

    async def register(self, data: RegisterRequest) -> User:
        if await self._repo.email_exists(data.email):
            raise AlreadyExistsError("Bu e-posta adresi zaten kullanılıyor.")

        return await self._repo.create(
            email=data.email.lower(),
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
        )

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

        user = await self._repo.get_by_id(payload.sub)
        if not user or not user.is_active:
            raise AuthenticationError("Kullanıcı bulunamadı.")

        tokens = create_token_pair(str(user.id))
        return TokenResponse(**tokens)

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
