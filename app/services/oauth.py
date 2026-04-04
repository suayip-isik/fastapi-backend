"""
OAuthService — Google ve GitHub sosyal giriş akışları.

Sorumluluklar: OAuth URL oluşturma · callback işleme · kullanıcı upsert
"""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.core.exceptions import ExternalServiceError, InvalidTokenError
from app.core.logging import get_logger
from app.core.redis import get_redis_client
from app.core.security import create_token_pair
from app.db.models.audit_log import AuditAction
from app.db.repositories.oauth_account import OAuthAccountRepository
from app.db.repositories.user import UserRepository
from app.schemas.auth import TokenResponse
from app.services._keys import OAUTH_STATE_KEY
from app.services.base import AuditableMixin

_logger = get_logger(__name__)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.audit import AuditService


class OAuthService(AuditableMixin):
    """Google ve GitHub OAuth 2.0 sosyal giriş akışlarını yöneten servis.

    Bu servis, OAuth 2.0 Authorization Code Grant akışını uygular:
    1. Kullanıcıyı provider'ın yetkilendirme sayfasına yönlendirir
    2. Callback'te authorization code'u access token ile değiştirir
    3. Kullanıcı bilgilerini çeker ve yerel hesap oluşturur/günceller
    4. JWT token çifti döndürür

    Attributes:
        _user_repo: Kullanıcı veritabanı işlemleri için repository.
        _oauth_repo: OAuth hesap kayıtları için repository.
        _audit: Giriş olaylarını loglamak için audit servisi.

    Example:
        >>> oauth_service = OAuthService(session, audit_service)
        >>> auth_url = await oauth_service.get_google_auth_url()
        >>> # Kullanıcı auth_url'e yönlendirilir, callback'te:
        >>> tokens = await oauth_service.google_callback(code, state)
    """

    def __init__(self, session: AsyncSession, audit: AuditService | None = None) -> None:
        """OAuthService örneği oluşturur.

        Args:
            session: Asenkron SQLAlchemy veritabanı oturumu.
            audit: İsteğe bağlı audit servisi. Verilirse giriş olayları loglanır.
        """
        self._user_repo = UserRepository(session)
        self._oauth_repo = OAuthAccountRepository(session)
        self._audit = audit

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _create_oauth_state(self) -> str:
        """CSRF koruması için rastgele state parametresi oluşturur ve Redis'e kaydeder.

        Returns:
            Redis'e kaydedilen state string'i (32 byte URL-safe random token).
        """
        state = secrets.token_urlsafe(32)
        redis = await get_redis_client()
        await redis.setex(OAUTH_STATE_KEY.format(state), 600, "1")
        return state

    # ── Google ────────────────────────────────────────────────────────────────

    async def get_google_auth_url(self) -> str:
        """Google OAuth yetkilendirme URL'i oluşturur.

        OAuth 2.0 Authorization Code Grant akışının ilk adımı olarak,
        kullanıcının Google hesabıyla giriş yapması için yetkilendirme
        URL'i oluşturur. CSRF koruması için rastgele state parametresi
        üretilir ve Redis'te 10 dakika süreyle saklanır.

        İstenen izinler (scopes):
            - openid: OpenID Connect kimlik doğrulama
            - email: Kullanıcının e-posta adresi
            - profile: Ad, profil fotoğrafı gibi temel bilgiler

        Returns:
            Google OAuth yetkilendirme sayfasına yönlendirme URL'i.

        Note:
            Frontend bu URL'e redirect yapmalıdır. Kullanıcı Google'da
            oturum açtıktan sonra callback URL'ine yönlendirilir.
        """
        state = await self._create_oauth_state()
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "state": state,
        }
        return f"https://accounts.google.com/o/oauth2/auth?{urlencode(params)}"

    async def google_callback(self, code: str, state: str) -> TokenResponse:
        """Google OAuth callback'ini işler ve JWT token çifti döndürür.

        Google'dan dönen authorization code'u access token ile değiştirir,
        kullanıcı bilgilerini Google API'den çeker ve yerel kullanıcı
        hesabını oluşturur veya günceller.

        OAuth akışı:
            1. State parametresini Redis'ten doğrular (CSRF koruması)
            2. Authorization code → access token değişimi
            3. Google userinfo endpoint'inden kullanıcı bilgilerini çeker
            4. Kullanıcıyı e-posta ile bulur veya yeni hesap oluşturur
            5. OAuthAccount kaydını upsert eder
            6. JWT access/refresh token çifti döndürür

        Args:
            code: Google'dan dönen authorization code.
            state: CSRF koruması için gönderilen state parametresi.

        Returns:
            Access ve refresh token içeren TokenResponse.

        Raises:
            InvalidTokenError: State parametresi geçersiz veya süresi dolmuşsa.
            httpx.HTTPStatusError: Google API çağrıları başarısız olursa.
        """
        redis = await get_redis_client()
        if not await redis.getdel(OAUTH_STATE_KEY.format(state)):
            raise InvalidTokenError("Geçersiz OAuth state parametresi.")

        try:
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
        except httpx.HTTPStatusError as exc:
            _logger.error(
                "oauth_callback_failed",
                provider="google",
                status_code=exc.response.status_code,
            )
            raise ExternalServiceError("Google kimlik doğrulaması başarısız.") from exc

        return await self._upsert_oauth_user(
            provider="google",
            provider_user_id=userinfo["sub"],
            email=userinfo["email"],
            full_name=userinfo.get("name"),
            avatar_url=userinfo.get("picture"),
            access_token=token_data.get("access_token"),
        )

    # ── GitHub ────────────────────────────────────────────────────────────────

    async def get_github_auth_url(self) -> str:
        """GitHub OAuth yetkilendirme URL'i oluşturur.

        OAuth 2.0 Authorization Code Grant akışının ilk adımı olarak,
        kullanıcının GitHub hesabıyla giriş yapması için yetkilendirme
        URL'i oluşturur. CSRF koruması için rastgele state parametresi
        üretilir ve Redis'te 10 dakika süreyle saklanır.

        İstenen izinler (scopes):
            - user:email: Kullanıcının e-posta adreslerini okuma

        Returns:
            GitHub OAuth yetkilendirme sayfasına yönlendirme URL'i.

        Note:
            GitHub, public profile bilgilerini varsayılan olarak verir.
            E-posta için ayrıca user:email scope'u gereklidir.
        """
        state = await self._create_oauth_state()
        params = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "redirect_uri": settings.GITHUB_REDIRECT_URI,
            "scope": "user:email",
            "state": state,
        }
        return f"https://github.com/login/oauth/authorize?{urlencode(params)}"

    async def github_callback(self, code: str, state: str) -> TokenResponse:
        """GitHub OAuth callback'ini işler ve JWT token çifti döndürür.

        GitHub'dan dönen authorization code'u access token ile değiştirir,
        kullanıcı bilgilerini GitHub API'den çeker ve yerel kullanıcı
        hesabını oluşturur veya günceller.

        OAuth akışı:
            1. State parametresini Redis'ten doğrular (CSRF koruması)
            2. Authorization code → access token değişimi
            3. GitHub /user endpoint'inden profil bilgilerini çeker
            4. GitHub /user/emails endpoint'inden primary e-postayı alır
            5. Kullanıcıyı e-posta ile bulur veya yeni hesap oluşturur
            6. OAuthAccount kaydını upsert eder
            7. JWT access/refresh token çifti döndürür

        Args:
            code: GitHub'dan dönen authorization code.
            state: CSRF koruması için gönderilen state parametresi.

        Returns:
            Access ve refresh token içeren TokenResponse.

        Raises:
            InvalidTokenError: State parametresi geçersiz veya süresi dolmuşsa.
            httpx.HTTPStatusError: GitHub API çağrıları başarısız olursa.

        Note:
            GitHub kullanıcısının birden fazla e-postası olabilir.
            Primary olarak işaretlenen e-posta tercih edilir.
        """
        redis = await get_redis_client()
        if not await redis.getdel(OAUTH_STATE_KEY.format(state)):
            raise InvalidTokenError("Geçersiz OAuth state parametresi.")

        try:
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
        except httpx.HTTPStatusError as exc:
            _logger.error(
                "oauth_callback_failed",
                provider="github",
                status_code=exc.response.status_code,
            )
            raise ExternalServiceError("GitHub kimlik doğrulaması başarısız.") from exc

        if not primary_email:
            raise ExternalServiceError("GitHub hesabından e-posta adresi alınamadı.")

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
        """OAuth kullanıcısını ve OAuthAccount kaydını bulur veya oluşturur.

        Hem Google hem GitHub callback'leri tarafından kullanılan ortak
        kullanıcı upsert mantığı. Provider-user_id çifti ile mevcut OAuth
        hesabı aranır; bulunursa token güncellenir, bulunamazsa yeni
        hesap oluşturulur.

        Upsert stratejisi:
            1. Provider + provider_user_id ile OAuthAccount ara
            2. Bulunduysa: Mevcut kullanıcıyı al, access_token'ı güncelle
            3. Bulunamadıysa:
               a. E-posta ile mevcut kullanıcı ara
               b. Yoksa yeni kullanıcı oluştur (is_verified=True)
               c. OAuthAccount kaydı oluştur

        Args:
            provider: OAuth sağlayıcı adı ("google" veya "github").
            provider_user_id: Sağlayıcıdaki kullanıcı ID'si.
            email: Kullanıcının e-posta adresi.
            full_name: Kullanıcının tam adı (opsiyonel).
            avatar_url: Profil fotoğrafı URL'i (opsiyonel).
            access_token: Provider'dan alınan access token (opsiyonel).

        Returns:
            Yeni oluşturulan JWT access ve refresh token çifti.

        Note:
            OAuth ile giriş yapan kullanıcılar otomatik olarak verified
            kabul edilir, çünkü e-posta provider tarafından doğrulanmıştır.
        """
        # 1. Provider kaydı var mı?
        oauth_account = await self._oauth_repo.get_by_provider(provider, provider_user_id)

        if oauth_account:
            # Bilinen provider — sadece token'i guncelle
            user = await self._user_repo.get_by_id_or_raise(oauth_account.user_id)
            await self._oauth_repo.update(oauth_account.id, access_token=access_token)
        else:
            # Yeni provider — kullaniciyi email ile bul ya da olustur
            existing = await self._user_repo.get_active_by_email(email)
            if not existing:
                existing = await self._user_repo.create(
                    email=email.lower(),
                    full_name=full_name,
                    avatar_url=avatar_url,
                    is_verified=True,
                )
            user = existing
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
