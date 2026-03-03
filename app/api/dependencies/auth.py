"""
FastAPI Dependency Injection katmanı.
Tüm ortak bağımlılıklar burada tanımlanır.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthenticationError,
    InsufficientPermissionsError,
    InvalidTokenError,
)
from app.core.redis import get_redis_client
from app.core.security import TokenType, decode_token
from app.db.models.user import User, UserRole
from app.db.repositories.user import UserRepository
from app.db.session import get_db

# ── Security Scheme ───────────────────────────────────────────────────────────

bearer_scheme = HTTPBearer(auto_error=False)

# ── DB Dependency ─────────────────────────────────────────────────────────────

DBDep = Annotated[AsyncSession, Depends(get_db)]

# ── Repository Dependencies ───────────────────────────────────────────────────


def get_user_repository(db: DBDep) -> UserRepository:
    return UserRepository(db)


UserRepoDep = Annotated[UserRepository, Depends(get_user_repository)]

# ── Auth Dependencies ─────────────────────────────────────────────────────────


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)],
    user_repo: UserRepoDep,
) -> User:
    """Bearer token'dan aktif kullanıcıyı çözer."""
    if not credentials:
        raise AuthenticationError("Authorization header eksik.")

    payload = decode_token(credentials.credentials)

    if payload.type != TokenType.ACCESS:
        raise InvalidTokenError("Yanlış token türü.")

    redis = await get_redis_client()
    if await redis.exists(f"blacklist:{payload.jti}"):
        raise InvalidTokenError("Token geçersiz kılınmış.")

    user = await user_repo.get_by_id(payload.sub)
    if not user or not user.is_active:
        raise AuthenticationError("Kullanıcı bulunamadı veya pasif.")

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Aktif kullanıcı. Endpoint'lerin büyük çoğunluğu bunu kullanır."""
    return current_user


def require_roles(*roles: UserRole):
    """Role-based access control factory."""

    async def check_role(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        if current_user.role not in roles:
            raise InsufficientPermissionsError(
                f"Bu işlem için gerekli rol: {', '.join(r.value for r in roles)}"
            )
        return current_user

    return check_role


# ── Type Aliases ──────────────────────────────────────────────────────────────

CurrentUserDep = Annotated[User, Depends(get_current_active_user)]
AdminDep = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
