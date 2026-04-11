"""
AuthService — email/password kimlik doğrulama ve token yönetimi.

Sorumluluklar: register · login · logout · refresh
Email doğrulama ve şifre sıfırlama → AccountService
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from app.adapters.infrastructure import ARQTaskQueueAdapter, RedisAdapter
from app.core.config import settings
from app.core.exceptions import (
    AuthenticationError,
    InvalidTokenError,
    TokenExpiredError,
    UserAlreadyExistsError,
)
from app.core.i18n import language_var, t
from app.core.security import (
    TokenType,
    create_token_pair,
    decode_token,
    hash_password,
    is_token_revoked_after,
    verify_password,
)
from app.db.models.audit_log import AuditAction
from app.db.models.user import SurfaceType, User
from app.db.repositories.user import UserRepository
from app.schemas.auth import PartialAuthResponse, RegisterRequest, TokenResponse
from app.services._keys import BLACKLIST_KEY, EMAIL_VERIFY_KEY, LOGIN_PARTIAL_KEY
from app.services.base import AuditableMixin
from app.services.totp import TOTPService
from app.tasks.worker import send_verification_email

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.ports.infrastructure import RedisPort, TaskQueuePort
    from app.services.audit import AuditService


def _encode_partial_login_value(user: User) -> str:
    return f"{user.id}|{datetime.now(UTC).isoformat()}"


def _decode_partial_login_value(raw_value: str) -> tuple[UUID, datetime | None]:
    if "|" not in raw_value:
        return UUID(raw_value), None
    user_id_str, issued_at_str = raw_value.split("|", 1)
    return UUID(user_id_str), datetime.fromisoformat(issued_at_str)


class AuthService(AuditableMixin):
    """Email/password tabanlı kimlik doğrulama servisi.

    Bu servis kullanıcı kaydı, giriş, çıkış ve token yenileme işlemlerini yönetir.
    Email doğrulama ve şifre sıfırlama için AccountService kullanılmalıdır.

    Attributes:
        _session: Veritabanı oturumu.
        _repo: Kullanıcı repository'si.
        _audit: Audit log servisi (opsiyonel).

    Example:
        >>> async with get_session() as session:
        ...     auth_service = AuthService(session, audit_service)
        ...     user = await auth_service.register(register_data)
        ...     tokens = await auth_service.login("user@example.com", "password123")
    """

    def __init__(self, session: AsyncSession, audit: AuditService | None = None) -> None:
        """AuthService örneği oluşturur.

        Veritabanı oturumu ve opsiyonel audit servisi ile servis başlatılır.
        UserRepository otomatik olarak oluşturulur.

        Args:
            session: SQLAlchemy async veritabanı oturumu. Tüm DB işlemleri
                bu oturum üzerinden gerçekleştirilir.
            audit: Audit log servisi. None ise audit logları atlanır.

        Note:
            Audit servisi sağlanmazsa, kimlik doğrulama işlemleri loglanmaz.
            Production ortamında audit servisi kullanılması önerilir.
        """
        self._session = session
        self._repo = UserRepository(session)
        self._audit = audit
        self._redis: RedisPort = RedisAdapter()
        self._task_queue: TaskQueuePort = ARQTaskQueueAdapter()

    def with_infrastructure(
        self,
        *,
        redis: RedisPort | None = None,
        task_queue: TaskQueuePort | None = None,
    ) -> AuthService:
        if redis is not None:
            self._redis = redis
        if task_queue is not None:
            self._task_queue = task_queue
        return self

    async def register(self, data: RegisterRequest) -> User:
        """Yeni kullanıcı kaydı oluşturur.

        Kullanıcı bilgilerini doğrular, şifreyi hashler, veritabanına kaydeder
        ve email doğrulama süreci başlatır. Email adresi otomatik olarak
        küçük harfe dönüştürülür.

        İş mantığı:
            1. Email adresinin benzersiz olduğunu kontrol eder
            2. Şifreyi bcrypt ile hashler (12 rounds)
            3. Kullanıcıyı veritabanına kaydeder (is_verified=False)
            4. 24 saat geçerli doğrulama token'ı oluşturur
            5. Doğrulama emailini ARQ worker üzerinden async gönderir
            6. Audit log kaydı oluşturur

        Args:
            data: Kayıt bilgilerini içeren Pydantic modeli.
                - email: Kullanıcının email adresi (benzersiz olmalı)
                - password: Düz metin şifre (min 8 karakter)
                - full_name: Kullanıcının tam adı (opsiyonel)

        Returns:
            User: Oluşturulan kullanıcı modeli. is_verified=False olarak döner.

        Raises:
            UserAlreadyExistsError: Belirtilen email adresi zaten kayıtlı ise.
            SQLAlchemyError: Veritabanı işlemi başarısız olursa.
            RedisError: Token Redis'e kaydedilemezse.

        Example:
            >>> data = RegisterRequest(
            ...     email="user@example.com",
            ...     password="SecurePass123!",
            ...     full_name="Ali Veli"
            ... )
            >>> user = await auth_service.register(data)
            >>> print(user.email)  # user@example.com
            >>> print(user.is_verified)  # False

        Note:
            - Email doğrulaması tamamlanmadan kullanıcı giriş yapamaz
            - Doğrulama token'ı 24 saat geçerlidir
            - Email gönderimi async olarak worker'da işlenir
        """
        if await self._repo.email_exists(data.email):
            raise UserAlreadyExistsError()

        user = await self._repo.create(
            email=data.email.lower(),
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
        )

        token = secrets.token_urlsafe(32)
        await self._redis.setex(
            EMAIL_VERIFY_KEY.format(token), settings.EMAIL_VERIFY_TTL, str(user.id)
        )
        await self._task_queue.enqueue(
            send_verification_email, user.email, token, language_var.get()
        )

        await self._audit_log(AuditAction.REGISTER, user_id=user.id)
        return user

    async def login(
        self,
        email: str,
        password: str,
        *,
        surface: SurfaceType = SurfaceType.CLIENT,
    ) -> TokenResponse | PartialAuthResponse:
        """Email ve şifre ile kullanıcı girişinin birinci adımı.

        Kimlik bilgilerini doğrular. TOTP aktif değilse tam token çifti,
        aktifse ikinci adım için partial_token döner.

        Returns:
            TokenResponse: TOTP yoksa tam JWT token çifti.
            PartialAuthResponse: TOTP aktifse partial_token ile challenge yanıtı.

        Raises:
            AuthenticationError: Email/şifre hatalı veya hesap aktif değil.

        Note:
            - Timing attack'lardan korunmak için hata mesajları generic tutulur
        """
        user = await self._repo.get_active_by_email(email, surface=surface)
        if not user or not user.hashed_password:
            await self._audit_log(AuditAction.LOGIN_FAILED, extra={"email": email})
            raise AuthenticationError(t("error.auth.invalid_credentials"))

        if not verify_password(password, user.hashed_password):
            await self._audit_log(AuditAction.LOGIN_FAILED, user_id=user.id)
            raise AuthenticationError(t("error.auth.invalid_credentials"))

        if user.totp_enabled:
            partial_token = secrets.token_urlsafe(32)
            await self._redis.setex(
                LOGIN_PARTIAL_KEY.format(partial_token),
                settings.LOGIN_PARTIAL_TTL,
                _encode_partial_login_value(user),
            )
            return PartialAuthResponse(partial_token=partial_token)

        await self._audit_log(AuditAction.LOGIN_SUCCESS, user_id=user.id)
        return TokenResponse(**create_token_pair(str(user.id)))

    async def complete_totp_login(self, partial_token: str, code: str) -> TokenResponse:
        """TOTP challenge'ı doğrulayarak login'i tamamlar (ikinci adım).

        partial_token ile Redis'teki kullanıcıyı bulur, TOTP kodunu doğrular
        ve tam JWT token çifti döner. Partial token tek kullanımlıktır.

        Args:
            partial_token: /auth/login adım 1'den alınan opaque token.
            code: 6 haneli TOTP kodu veya 8 karakterli backup kodu.

        Returns:
            TokenResponse: Tam JWT token çifti (access + refresh).

        Raises:
            AuthenticationError: Geçersiz/süresi dolmuş partial_token veya hatalı TOTP kodu.
        """
        partial_value = await self._redis.get(LOGIN_PARTIAL_KEY.format(partial_token))
        if not partial_value:
            raise AuthenticationError(t("error.auth.invalid_session"))

        await self._redis.delete(LOGIN_PARTIAL_KEY.format(partial_token))

        user_id, issued_at = _decode_partial_login_value(partial_value)
        user = await self._repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise AuthenticationError(t("error.auth.account_inactive"))
        if issued_at and is_token_revoked_after(issued_at, user.session_revoked_after):
            raise AuthenticationError(t("error.auth.invalid_session"))

        totp_svc = TOTPService(self._session, redis=self._redis)
        await totp_svc.check_login(user, code)

        await self._audit_log(AuditAction.LOGIN_SUCCESS, user_id=user.id)
        return TokenResponse(**create_token_pair(str(user.id)))

    async def refresh(self, refresh_token: str) -> TokenResponse:
        """Refresh token kullanarak yeni access token alır.

        Geçerli bir refresh token ile yeni bir token çifti oluşturur. Güvenlik için
        token rotation uygulanır: kullanılan refresh token blacklist'e eklenir.

        İş mantığı:
            1. Refresh token'ı decode eder ve imzasını doğrular
            2. Token türünün REFRESH olduğunu kontrol eder
            3. Token'ın blacklist'te olmadığını doğrular
            4. Kullanıcının hala aktif olduğunu kontrol eder
            5. Eski refresh token'ı blacklist'e ekler (rotation)
            6. Yeni access ve refresh token çifti oluşturur

        Args:
            refresh_token: Geçerli bir JWT refresh token. Login veya önceki
                refresh işleminden alınmış olmalıdır.

        Returns:
            TokenResponse: Yeni JWT token çiftini içeren response.
                - access_token: Yeni 30 dakikalık access token
                - refresh_token: Yeni 30 günlük refresh token
                - token_type: "Bearer"

        Raises:
            InvalidTokenError: Aşağıdaki durumlarda fırlatılır:
                - Token decode edilemezse (bozuk/geçersiz imza)
                - Token türü REFRESH değilse
                - Token blacklist'te ise (zaten kullanılmış)
            TokenExpiredError: Refresh token süresi dolmuşsa (30 gün).
            AuthenticationError: Kullanıcı bulunamaz veya aktif değilse.

        Example:
            >>> # Access token süresi dolduğunda
            >>> new_tokens = await auth_service.refresh(old_refresh_token)
            >>> # Artık old_refresh_token kullanılamaz (blacklist'te)

        Note:
            - Token rotation sayesinde çalınmış refresh token sadece 1 kez kullanılabilir
            - Blacklist TTL'i token'ın kalan süresine eşittir (gereksiz veri tutulmaz)
            - Her refresh işlemi audit log'a kaydedilir
        """
        payload = decode_token(refresh_token)
        if payload.type != TokenType.REFRESH:
            raise InvalidTokenError(t("error.auth.token_type_invalid"))

        if await self._redis.exists(BLACKLIST_KEY.format(payload.jti)):
            raise InvalidTokenError(t("error.auth.token_revoked"))

        user = await self._repo.get_by_id(UUID(payload.sub))
        if not user or not user.is_active:
            raise AuthenticationError(t("error.auth.user_not_found"))
        if is_token_revoked_after(payload.iat, user.session_revoked_after):
            raise InvalidTokenError(t("error.auth.token_revoked"))

        # Eski refresh token'ı blacklist'e ekle (rotation)
        remaining = int((payload.exp - datetime.now(UTC)).total_seconds())
        if remaining > 0:
            await self._redis.setex(BLACKLIST_KEY.format(payload.jti), remaining, "1")

        await self._audit_log(AuditAction.TOKEN_REFRESHED, user_id=user.id)
        tokens = create_token_pair(str(user.id))
        return TokenResponse(**tokens)

    async def logout(
        self, access_token: str, refresh_token: str | None, user_id: UUID | None = None
    ) -> None:
        """Kullanıcı oturumunu sonlandırır ve token'ları geçersiz kılar.

        Access ve refresh token'ları Redis blacklist'ine ekleyerek geçersiz kılar.
        Logout işlemi her zaman başarılı olur; geçersiz refresh token logout'u engellemez.

        İş mantığı:
            1. Access token'ı decode eder ve blacklist'e ekler
            2. Refresh token varsa decode etmeye çalışır
            3. Geçerli refresh token'ı blacklist'e ekler
            4. Geçersiz/süresi dolmuş refresh token sessizce atlanır
            5. Audit log kaydı oluşturur

        Args:
            access_token: Kullanıcının mevcut access token'ı. Authorization
                header'dan alınmalıdır.
            refresh_token: Kullanıcının refresh token'ı. İstemci tarafından
                sağlanır, opsiyoneldir.
            user_id: Logout yapan kullanıcının ID'si. Audit log için kullanılır.
                None ise audit log'da kullanıcı belirtilmez.

        Returns:
            None: Logout işlemi sessizce tamamlanır.

        Raises:
            InvalidTokenError: Access token decode edilemezse.
            TokenExpiredError: Access token süresi dolmuşsa.
            RedisError: Redis bağlantısı başarısız olursa.

        Example:
            >>> # Tam logout (access + refresh)
            >>> await auth_service.logout(
            ...     access_token="eyJ...",
            ...     refresh_token="eyJ...",
            ...     user_id=user.id
            ... )
            >>>
            >>> # Sadece access token ile logout
            >>> await auth_service.logout(access_token="eyJ...", refresh_token=None)

        Note:
            - Blacklist TTL'i token'ın kalan süresine eşittir
            - Süresi dolmuş token'lar blacklist'e eklenmez (gereksiz)
            - Refresh token hataları sessizce yutulur (kullanıcı deneyimi)
            - Tüm cihazlardan çıkış için ayrı bir mekanizma gerekir
        """
        access_payload = decode_token(access_token)
        remaining = int((access_payload.exp - datetime.now(UTC)).total_seconds())
        if remaining > 0:
            await self._redis.setex(BLACKLIST_KEY.format(access_payload.jti), remaining, "1")

        if refresh_token:
            try:
                refresh_payload = decode_token(refresh_token)
                if refresh_payload.type == TokenType.REFRESH:
                    remaining = int((refresh_payload.exp - datetime.now(UTC)).total_seconds())
                    if remaining > 0:
                        await self._redis.setex(
                            BLACKLIST_KEY.format(refresh_payload.jti), remaining, "1"
                        )
            except (InvalidTokenError, TokenExpiredError):
                # Geçersiz veya süresi dolmuş refresh token logout'u engellemez
                pass

        await self._audit_log(AuditAction.LOGOUT, user_id=user_id)
