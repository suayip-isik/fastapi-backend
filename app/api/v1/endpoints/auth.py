"""
Auth endpoint'leri — sadece HTTP katmanı.
Business logic AuthService'te.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUserDep
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    OAuthCallbackRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


def get_auth_service(db: Annotated[AsyncSession, Depends(get_db)]) -> AuthService:
    return AuthService(db)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


# ── Email/Password ────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserResponse, status_code=201)
async def register(data: RegisterRequest, service: AuthServiceDep):
    """Yeni kullanıcı kaydı."""
    user = await service.register(data)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, service: AuthServiceDep):
    """Email/password ile giriş."""
    return await service.login(data.email, data.password)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(data: RefreshRequest, service: AuthServiceDep):
    """Refresh token ile yeni access token al."""
    return await service.refresh(data.refresh_token)


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


# ── Me ────────────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUserDep):
    """Aktif kullanıcı bilgisi."""
    return current_user
