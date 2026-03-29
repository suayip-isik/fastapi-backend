"""
OAuthService — Google ve GitHub sosyal giriş akışları.

Sorumluluklar: OAuth URL oluşturma · callback işleme · kullanıcı upsert
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from app.core.config import settings
from app.core.security import create_token_pair
from app.db.models.audit_log import AuditAction
from app.db.repositories.oauth_account import OAuthAccountRepository
from app.db.repositories.user import UserRepository
from app.schemas.auth import TokenResponse
from app.services.base import AuditableMixin

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.audit import AuditService


class OAuthService(AuditableMixin):
    def __init__(self, session: AsyncSession, audit: AuditService | None = None) -> None:
        self._user_repo = UserRepository(session)
        self._oauth_repo = OAuthAccountRepository(session)
        self._audit = audit

    # ── Google ────────────────────────────────────────────────────────────────

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

    # ── GitHub ────────────────────────────────────────────────────────────────

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
        """OAuth kullanıcısını ve OAuthAccount kaydını bul ya da oluştur."""
        # 1. Provider kaydı var mı?
        oauth_account = await self._oauth_repo.get_by_provider(provider, provider_user_id)

        if oauth_account:
            # Bilinen provider — sadece token'ı güncelle
            user = await self._user_repo.get_by_id(oauth_account.user_id)
            await self._oauth_repo.update(oauth_account.id, access_token=access_token)
        else:
            # Yeni provider — kullanıcıyı email ile bul ya da oluştur
            user = await self._user_repo.get_active_by_email(email)
            if not user:
                user = await self._user_repo.create(
                    email=email.lower(),
                    full_name=full_name,
                    avatar_url=avatar_url,
                    is_verified=True,  # OAuth ile gelen email doğrulanmış sayılır
                )
            await self._oauth_repo.upsert(
                user_id=user.id,
                provider=provider,
                provider_user_id=provider_user_id,
                email=email,
                access_token=access_token,
            )

        await self._audit_log(AuditAction.LOGIN_SUCCESS, user_id=user.id)
        tokens = create_token_pair(str(user.id))
        return TokenResponse(**tokens)
