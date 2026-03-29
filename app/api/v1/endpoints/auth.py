"""
Auth endpoint'leri — sadece HTTP katmani.
Business logic ilgili service'te.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Security
from fastapi.responses import RedirectResponse
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
    RefreshRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.schemas.common import MessageResponse
from app.schemas.user import UserResponse
from app.services.account import AccountService
from app.services.audit import AuditService
from app.services.auth import AuthService
from app.services.oauth import OAuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


# ── Dependency factories ──────────────────────────────────────────────────────


def get_audit_service() -> AuditService:
    return AuditService()


AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]


def get_auth_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    audit: AuditServiceDep,
) -> AuthService:
    return AuthService(db, audit)


def get_oauth_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    audit: AuditServiceDep,
) -> OAuthService:
    return OAuthService(db, audit)


def get_account_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    audit: AuditServiceDep,
) -> AccountService:
    return AccountService(db, audit)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
OAuthServiceDep = Annotated[OAuthService, Depends(get_oauth_service)]
AccountServiceDep = Annotated[AccountService, Depends(get_account_service)]


# ── Email/Password ────────────────────────────────────────────────────────────


@router.post("/register", response_model=UserResponse, status_code=201)
@limiter.limit(settings.RATE_LIMIT_REGISTER)
async def register(request: Request, data: RegisterRequest, service: AuthServiceDep) -> User:
    """Yeni kullanici kaydi."""
    return await service.register(data)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def login(request: Request, data: LoginRequest, service: AuthServiceDep) -> TokenResponse:
    """Email/password ile giris."""
    return await service.login(data.email, data.password)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(data: RefreshRequest, service: AuthServiceDep) -> TokenResponse:
    """Refresh token ile yeni access token al. Eski refresh token gecersiz kilinir (rotation)."""
    return await service.refresh(data.refresh_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    data: LogoutRequest,
    current_user: CurrentUserDep,
    credentials: Annotated[HTTPAuthorizationCredentials, Security(bearer_scheme)],
    service: AuthServiceDep,
) -> MessageResponse:
    """Oturumu kapat. Access ve refresh token'lari blacklist'e ekler."""
    await service.logout(credentials.credentials, data.refresh_token, user_id=current_user.id)
    return MessageResponse(message="Basariyla cikis yapildi.")


# ── Google OAuth ──────────────────────────────────────────────────────────────


@router.get("/google")
async def google_login(service: OAuthServiceDep) -> RedirectResponse:
    """Google OAuth akisini baslat."""
    return RedirectResponse(service.get_google_auth_url())


@router.get("/google/callback", response_model=TokenResponse)
async def google_callback(code: str, service: OAuthServiceDep) -> TokenResponse:
    """Google OAuth callback."""
    return await service.google_callback(code)


# ── GitHub OAuth ──────────────────────────────────────────────────────────────


@router.get("/github")
async def github_login(service: OAuthServiceDep) -> RedirectResponse:
    """GitHub OAuth akisini baslat."""
    return RedirectResponse(service.get_github_auth_url())


@router.get("/github/callback", response_model=TokenResponse)
async def github_callback(code: str, service: OAuthServiceDep) -> TokenResponse:
    """GitHub OAuth callback."""
    return await service.github_callback(code)


# ── Email Verification ────────────────────────────────────────────────────────


@router.post("/verify-email", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def verify_email(
    request: Request, data: VerifyEmailRequest, service: AccountServiceDep
) -> MessageResponse:
    """E-posta adresini dogrula."""
    await service.verify_email(data.token)
    return MessageResponse(message="E-posta adresiniz basariyla dogrulandi.")


@router.post("/resend-verification", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH_EMAIL)
async def resend_verification(
    request: Request, data: ResendVerificationRequest, service: AccountServiceDep
) -> MessageResponse:
    """Dogrulama e-postasini yeniden gonder."""
    await service.resend_verification(data.email)
    return MessageResponse(message="Dogrulama e-postasi gonderildi.")


# ── Password Reset ────────────────────────────────────────────────────────────


@router.post("/forgot-password", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH_EMAIL)
async def forgot_password(
    request: Request, data: ForgotPasswordRequest, service: AccountServiceDep
) -> MessageResponse:
    """Sifre sifirlama e-postasi gonder. Kullanici varligini aciklamaz."""
    await service.forgot_password(data.email)
    return MessageResponse(message="Sifre sifirlama talimatlari e-posta adresinize gonderildi.")


@router.post("/reset-password", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def reset_password(
    request: Request, data: ResetPasswordRequest, service: AccountServiceDep
) -> MessageResponse:
    """Token ile sifreyi sifirla."""
    await service.reset_password(data.token, data.new_password)
    return MessageResponse(message="Sifreniz basariyla sifirlandi.")


# ── Me ────────────────────────────────────────────────────────────────────────


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUserDep) -> User:
    """Aktif kullanici bilgisi."""
    return current_user
