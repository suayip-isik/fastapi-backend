"""
Auth endpoint'leri — sadece HTTP katmanı.
Business logic AuthService'te.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Security
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUserDep, bearer_scheme
from app.core.config import settings
from app.core.limiter import limiter
from app.db.session import get_db
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    OAuthCallbackRequest,
    RefreshRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.schemas.common import MessageResponse
from app.schemas.user import UserResponse
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


def get_auth_service(db: Annotated[AsyncSession, Depends(get_db)]) -> AuthService:
    return AuthService(db)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


# ── Email/Password ────────────────────────────────────────────────────────────


@router.post("/register", response_model=UserResponse, status_code=201)
@limiter.limit(settings.RATE_LIMIT_REGISTER)
async def register(request: Request, data: RegisterRequest, service: AuthServiceDep):
    """Yeni kullanıcı kaydı."""
    user = await service.register(data)
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def login(request: Request, data: LoginRequest, service: AuthServiceDep):
    """Email/password ile giriş."""
    return await service.login(data.email, data.password)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(data: RefreshRequest, service: AuthServiceDep):
    """Refresh token ile yeni access token al. Eski refresh token geçersiz kılınır (rotation)."""
    return await service.refresh(data.refresh_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    data: LogoutRequest,
    current_user: CurrentUserDep,
    credentials: Annotated[HTTPAuthorizationCredentials, Security(bearer_scheme)],
    service: AuthServiceDep,
):
    """Oturumu kapat. Access ve refresh token'ları blacklist'e ekler."""
    await service.logout(credentials.credentials, data.refresh_token)
    return MessageResponse(message="Başarıyla çıkış yapıldı.")


# ── Google OAuth ──────────────────────────────────────────────────────────────


@router.get("/google")
async def google_login(service: AuthServiceDep):
    """Google OAuth akışını başlat."""
    url = service.get_google_auth_url()
    return RedirectResponse(url)


@router.get("/google/callback", response_model=TokenResponse)
async def google_callback(code: str, service: AuthServiceDep):
    """Google OAuth callback."""
    return await service.google_callback(code)


# ── GitHub OAuth ──────────────────────────────────────────────────────────────


@router.get("/github")
async def github_login(service: AuthServiceDep):
    """GitHub OAuth akışını başlat."""
    url = service.get_github_auth_url()
    return RedirectResponse(url)


@router.get("/github/callback", response_model=TokenResponse)
async def github_callback(code: str, service: AuthServiceDep):
    """GitHub OAuth callback."""
    return await service.github_callback(code)


# ── Email Verification ────────────────────────────────────────────────────────


@router.post("/verify-email", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def verify_email(request: Request, data: VerifyEmailRequest, service: AuthServiceDep):
    """E-posta adresini doğrula."""
    await service.verify_email(data.token)
    return MessageResponse(message="E-posta adresiniz başarıyla doğrulandı.")


@router.post("/resend-verification", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH_EMAIL)
async def resend_verification(
    request: Request, data: ResendVerificationRequest, service: AuthServiceDep
):
    """Doğrulama e-postasını yeniden gönder."""
    await service.resend_verification(data.email)
    return MessageResponse(message="Doğrulama e-postası gönderildi.")


# ── Password Reset ────────────────────────────────────────────────────────────


@router.post("/forgot-password", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH_EMAIL)
async def forgot_password(request: Request, data: ForgotPasswordRequest, service: AuthServiceDep):
    """Şifre sıfırlama e-postası gönder. Kullanıcı varlığını açıklamaz."""
    await service.forgot_password(data.email)
    return MessageResponse(message="Şifre sıfırlama talimatları e-posta adresinize gönderildi.")


@router.post("/reset-password", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def reset_password(request: Request, data: ResetPasswordRequest, service: AuthServiceDep):
    """Token ile şifreyi sıfırla."""
    await service.reset_password(data.token, data.new_password)
    return MessageResponse(message="Şifreniz başarıyla sıfırlandı.")


# ── Me ────────────────────────────────────────────────────────────────────────


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUserDep):
    """Aktif kullanıcı bilgisi."""
    return current_user
