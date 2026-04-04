"""
Kimlik Doğrulama (Auth) Endpoint'leri.

Bu modül, kullanıcı kimlik doğrulama işlemlerini yönetir:
- Email/şifre ile kayıt ve giriş
- JWT token yönetimi (access/refresh)
- E-posta doğrulama ve şifre sıfırlama

Not:
    Tüm business logic ilgili service katmanında yer alır.
    Bu endpoint'ler yalnızca HTTP katmanı görevini üstlenir.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Security
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUserDep, bearer_scheme
from app.core.config import settings
from app.core.limiter import limiter
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    PartialAuthResponse,
    RefreshRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    TOTPChallengeRequest,
    VerifyEmailRequest,
)
from app.schemas.common import MessageResponse
from app.schemas.user import UserResponse
from app.services.account import AccountService
from app.services.audit import AuditService
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


# ── Dependency factories ──────────────────────────────────────────────────────


def get_audit_service() -> AuditService:
    """get_audit_service işlemini gerçekleştirir."""
    return AuditService()


AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]


def get_auth_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    audit: AuditServiceDep,
) -> AuthService:
    """get_auth_service işlemini gerçekleştirir."""
    return AuthService(db, audit)


def get_account_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    audit: AuditServiceDep,
) -> AccountService:
    """get_account_service işlemini gerçekleştirir."""
    return AccountService(db, audit)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
AccountServiceDep = Annotated[AccountService, Depends(get_account_service)]


# ── Email/Password ────────────────────────────────────────────────────────────


@router.post("/register", response_model=UserResponse, status_code=201)
@limiter.limit(settings.RATE_LIMIT_REGISTER)
async def register(request: Request, data: RegisterRequest, service: AuthServiceDep) -> User:
    """
    Yeni kullanıcı kaydı oluşturur.

    Verilen bilgilerle sisteme yeni bir kullanıcı kaydeder.
    Kayıt sonrası kullanıcıya doğrulama e-postası gönderilir.

    Args:
        request: FastAPI Request nesnesi (rate limiting için).
        data: Kayıt bilgileri.
            - email (str): Kullanıcı e-posta adresi (benzersiz olmalı).
            - password (str): Şifre (min 8 karakter, büyük/küçük harf, rakam).
            - full_name (str, optional): Tam ad.

    Returns:
        UserResponse: Oluşturulan kullanıcı bilgileri.
            - id (UUID): Kullanıcı kimliği.
            - email (str): E-posta adresi.
            - full_name (str): Tam ad.
            - is_verified (bool): E-posta doğrulama durumu.
            - created_at (datetime): Oluşturulma zamanı.

    Raises:
        HTTPException 400: E-posta zaten kayıtlı.
        HTTPException 422: Geçersiz veri formatı.
        HTTPException 429: Rate limit aşıldı.

    Example:
        ```bash
        curl -X POST http://localhost:8000/api/v1/auth/register \\
            -H "Content-Type: application/json" \\
            -d '{"email": "user@example.com", "password": "Secure123!", "full_name": "Ali Veli"}'
        ```
    """
    return await service.register(data)


@router.post("/login", response_model=TokenResponse | PartialAuthResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def login(
    request: Request, data: LoginRequest, service: AuthServiceDep
) -> TokenResponse | PartialAuthResponse:
    """
    E-posta ve şifre ile kullanıcı girişinin birinci adımı.

    TOTP aktif değilse tam JWT token çifti döner.
    TOTP aktifse partial_token içeren yanıt döner;
    ikinci adım için /auth/totp-challenge kullanılır.

    Args:
        request: FastAPI Request nesnesi (rate limiting için).
        data: Giriş bilgileri.
            - email (str): Kayıtlı e-posta adresi.
            - password (str): Kullanıcı şifresi.

    Returns:
        TokenResponse: TOTP yoksa JWT token çifti (access + refresh).
        PartialAuthResponse: TOTP aktifse {requires_totp: true, partial_token: str}.

    Raises:
        HTTPException 401: Geçersiz e-posta veya şifre.
        HTTPException 429: Rate limit aşıldı.

    Example:
        ```bash
        curl -X POST http://localhost:8000/api/v1/auth/login \\
            -H "Content-Type: application/json" \\
            -d '{"email": "user@example.com", "password": "Secure123!"}'
        ```
    """
    return await service.login(data.email, data.password)


@router.post("/totp-challenge", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def totp_challenge(
    request: Request, data: TOTPChallengeRequest, service: AuthServiceDep
) -> TokenResponse:
    """
    TOTP challenge'ı doğrulayarak login'i tamamlar (ikinci adım).

    /auth/login'den alınan partial_token ve authenticator uygulamasındaki
    TOTP kodu (veya backup kodu) ile kimlik doğrulamayı tamamlar.
    Partial token tek kullanımlıktır ve 5 dakika geçerlidir.

    Args:
        request: FastAPI Request nesnesi (rate limiting için).
        data: Challenge bilgileri.
            - partial_token (str): /auth/login'den alınan kısa ömürlü token.
            - code (str): 6 haneli TOTP kodu veya 8 karakterli backup kodu.

    Returns:
        TokenResponse: JWT token çifti.
            - access_token (str): Erişim token'ı (30 dakika).
            - refresh_token (str): Yenileme token'ı (30 gün).
            - token_type (str): "bearer".

    Raises:
        HTTPException 401: Geçersiz veya süresi dolmuş partial_token.
        HTTPException 401: Hatalı TOTP kodu veya backup kodu.
        HTTPException 429: Rate limit aşıldı.

    Example:
        ```bash
        curl -X POST http://localhost:8000/api/v1/auth/totp-challenge \\
            -H "Content-Type: application/json" \\
            -d '{"partial_token": "xyz...", "code": "123456"}'
        ```
    """
    return await service.complete_totp_login(data.partial_token, data.code)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(data: RefreshRequest, service: AuthServiceDep) -> TokenResponse:
    """
    Refresh token ile yeni access token alır.

    Token rotation prensibi uygulanır: Her kullanımda eski refresh token
    geçersiz kılınır ve yeni bir çift token döner. Bu, çalınmış token'ların
    tekrar kullanılmasını engeller.

    Args:
        data: Yenileme isteği.
            - refresh_token (str): Geçerli refresh token.

    Returns:
        TokenResponse: Yeni JWT token çifti.
            - access_token (str): Yeni erişim token'ı (30 dakika).
            - refresh_token (str): Yeni yenileme token'ı (30 gün).
            - token_type (str): "bearer".

    Raises:
        HTTPException 401: Geçersiz, süresi dolmuş veya iptal edilmiş token.
        HTTPException 401: Token zaten kullanılmış (replay attack).

    Example:
        ```bash
        curl -X POST http://localhost:8000/api/v1/auth/refresh \\
            -H "Content-Type: application/json" \\
            -d '{"refresh_token": "eyJhbGciOiJSUzI1NiIs..."}'
        ```
    """
    return await service.refresh(data.refresh_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    data: LogoutRequest,
    current_user: CurrentUserDep,
    credentials: Annotated[HTTPAuthorizationCredentials, Security(bearer_scheme)],
    service: AuthServiceDep,
) -> MessageResponse:
    """
    Kullanıcı oturumunu sonlandırır.

    Hem access token hem de refresh token blacklist'e eklenir.
    Bu token'lar artık hiçbir işlemde kullanılamaz.

    Args:
        data: Çıkış isteği.
            - refresh_token (str): İptal edilecek refresh token.
        current_user: Oturum açmış kullanıcı (otomatik enjekte edilir).
        credentials: Bearer token (Authorization header'dan).
        service: Auth servisi.

    Returns:
        MessageResponse: Başarı mesajı.
            - message (str): "Başarıyla çıkış yapıldı."

    Raises:
        HTTPException 401: Geçersiz veya eksik access token.

    Note:
        Tüm cihazlardan çıkış yapmak için `/logout-all` endpoint'ini kullanın.

    Example:
        ```bash
        curl -X POST http://localhost:8000/api/v1/auth/logout \\
            -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..." \\
            -H "Content-Type: application/json" \\
            -d '{"refresh_token": "eyJhbGciOiJSUzI1NiIs..."}'
        ```
    """
    await service.logout(credentials.credentials, data.refresh_token, user_id=current_user.id)
    return MessageResponse(message="Basariyla cikis yapildi.")


# ── Email Verification ────────────────────────────────────────────────────────


@router.post("/verify-email", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def verify_email(
    request: Request, data: VerifyEmailRequest, service: AccountServiceDep
) -> MessageResponse:
    """
    E-posta adresini doğrulama token'ı ile doğrular.

    Kayıt sonrası gönderilen doğrulama e-postasındaki linkteki
    token kullanılarak e-posta adresi doğrulanır.

    Args:
        request: FastAPI Request nesnesi (rate limiting için).
        data: Doğrulama isteği.
            - token (str): E-posta ile gönderilen doğrulama token'ı.

    Returns:
        MessageResponse: Başarı mesajı.
            - message (str): "E-posta adresiniz başarıyla doğrulandı."

    Raises:
        HTTPException 400: Geçersiz veya süresi dolmuş token.
        HTTPException 400: E-posta zaten doğrulanmış.
        HTTPException 429: Rate limit aşıldı.

    Note:
        Token tek kullanımlıktır ve varsayılan olarak 24 saat geçerlidir.
        Yeni token için `/resend-verification` endpoint'ini kullanın.

    Example:
        ```bash
        curl -X POST http://localhost:8000/api/v1/auth/verify-email \\
            -H "Content-Type: application/json" \\
            -d '{"token": "eyJhbGciOiJIUzI1NiIs..."}'
        ```
    """
    await service.verify_email(data.token)
    return MessageResponse(message="E-posta adresiniz başarıyla doğrulandı.")


@router.post("/resend-verification", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH_EMAIL)
async def resend_verification(
    request: Request, data: ResendVerificationRequest, service: AccountServiceDep
) -> MessageResponse:
    """
    E-posta doğrulama linkini yeniden gönderir.

    Önceki doğrulama token'ının süresi dolduysa veya e-posta ulaşmadıysa
    yeni bir doğrulama e-postası gönderir.

    Args:
        request: FastAPI Request nesnesi (rate limiting için).
        data: Yeniden gönderim isteği.
            - email (str): Doğrulama e-postası gönderilecek adres.

    Returns:
        MessageResponse: Başarı mesajı.
            - message (str): "Doğrulama e-postası gönderildi."

    Raises:
        HTTPException 400: E-posta zaten doğrulanmış.
        HTTPException 429: Rate limit aşıldı (e-posta spam koruması).

    Note:
        Güvenlik nedeniyle, kayıtlı olmayan e-postalar için de
        aynı başarı mesajı döner (user enumeration koruması).

    Example:
        ```bash
        curl -X POST http://localhost:8000/api/v1/auth/resend-verification \\
            -H "Content-Type: application/json" \\
            -d '{"email": "user@example.com"}'
        ```
    """
    await service.resend_verification(data.email)
    return MessageResponse(message="Dogrulama e-postasi gonderildi.")


# ── Password Reset ────────────────────────────────────────────────────────────


@router.post("/forgot-password", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH_EMAIL)
async def forgot_password(
    request: Request, data: ForgotPasswordRequest, service: AccountServiceDep
) -> MessageResponse:
    """
    Şifre sıfırlama e-postası gönderir.

    Kayıtlı e-posta adresine şifre sıfırlama linki içeren
    bir e-posta gönderir.

    Args:
        request: FastAPI Request nesnesi (rate limiting için).
        data: Şifre sıfırlama isteği.
            - email (str): Kayıtlı e-posta adresi.

    Returns:
        MessageResponse: Başarı mesajı.
            - message (str): "Şifre sıfırlama talimatları e-posta adresinize gönderildi."

    Raises:
        HTTPException 429: Rate limit aşıldı (e-posta spam koruması).

    Note:
        Güvenlik nedeniyle, kullanıcının var olup olmadığı açıklanmaz.
        Her durumda aynı başarı mesajı döner (user enumeration koruması).
        Şifre sıfırlama token'ı varsayılan olarak 1 saat geçerlidir.

    Example:
        ```bash
        curl -X POST http://localhost:8000/api/v1/auth/forgot-password \\
            -H "Content-Type: application/json" \\
            -d '{"email": "user@example.com"}'
        ```
    """
    await service.forgot_password(data.email)
    return MessageResponse(message="Sifre sifirlama talimatlari e-posta adresinize gonderildi.")


@router.post("/reset-password", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def reset_password(
    request: Request, data: ResetPasswordRequest, service: AccountServiceDep
) -> MessageResponse:
    """
    Şifre sıfırlama token'ı ile yeni şifre belirler.

    `/forgot-password` ile gönderilen e-postadaki linkteki token
    kullanılarak şifre sıfırlanır.

    Args:
        request: FastAPI Request nesnesi (rate limiting için).
        data: Şifre sıfırlama bilgileri.
            - token (str): E-posta ile gönderilen sıfırlama token'ı.
            - new_password (str): Yeni şifre (min 8 karakter, güçlü olmalı).

    Returns:
        MessageResponse: Başarı mesajı.
            - message (str): "Şifreniz başarıyla sıfırlandı."

    Raises:
        HTTPException 400: Geçersiz veya süresi dolmuş token.
        HTTPException 400: Token zaten kullanılmış.
        HTTPException 422: Yeni şifre gereksinimleri karşılamıyor.
        HTTPException 429: Rate limit aşıldı.

    Note:
        Token tek kullanımlıktır. Sıfırlama sonrası tüm aktif
        oturumlar sonlandırılır (güvenlik önlemi).

    Example:
        ```bash
        curl -X POST http://localhost:8000/api/v1/auth/reset-password \\
            -H "Content-Type: application/json" \\
            -d '{"token": "eyJhbGciOiJIUzI1NiIs...", "new_password": "NewSecure123!"}'
        ```
    """
    await service.reset_password(data.token, data.new_password)
    return MessageResponse(message="Sifreniz basariyla sifirlandi.")


# ── Me ────────────────────────────────────────────────────────────────────────


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUserDep) -> User:
    """
    Oturum açmış kullanıcının bilgilerini döner.

    Access token ile kimliği doğrulanmış kullanıcının
    profil bilgilerini getirir.

    Args:
        current_user: Oturum açmış kullanıcı (otomatik enjekte edilir).

    Returns:
        UserResponse: Kullanıcı bilgileri.
            - id (UUID): Kullanıcı kimliği.
            - email (str): E-posta adresi.
            - full_name (str | None): Tam ad.
            - is_verified (bool): E-posta doğrulama durumu.
            - is_active (bool): Hesap aktiflik durumu.
            - role (str): Kullanıcı rolü (user, admin, vb.).
            - created_at (datetime): Hesap oluşturulma zamanı.
            - updated_at (datetime): Son güncelleme zamanı.

    Raises:
        HTTPException 401: Geçersiz veya eksik access token.
        HTTPException 401: Token süresi dolmuş.
        HTTPException 403: Hesap devre dışı veya askıya alınmış.

    Example:
        ```bash
        curl -X GET http://localhost:8000/api/v1/auth/me \\
            -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIs..."
        ```
    """
    return current_user
