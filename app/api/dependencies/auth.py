"""
FastAPI Dependency Injection katmanı.
Tüm ortak bağımlılıklar burada tanımlanır.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Any
from uuid import UUID

from fastapi import Depends, Header, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthenticationError,
    InsufficientPermissionsError,
    InvalidTokenError,
)
from app.core.redis import get_redis_client
from app.core.security import TokenType, decode_token
from app.db.models.user import User
from app.db.repositories.user import UserRepository
from app.db.session import get_db
from app.services._keys import BLACKLIST_KEY, USER_PERMISSIONS_KEY, USER_PERMISSIONS_TTL

if TYPE_CHECKING:
    from app.core.permissions import Permission

# ── Security Scheme ───────────────────────────────────────────────────────────

bearer_scheme = HTTPBearer(auto_error=False)

# ── DB Dependency ─────────────────────────────────────────────────────────────

DBDep = Annotated[AsyncSession, Depends(get_db)]

# ── Repository Dependencies ───────────────────────────────────────────────────


def get_user_repository(db: DBDep) -> UserRepository:
    return UserRepository(db)


UserRepoDep = Annotated[UserRepository, Depends(get_user_repository)]

# ── Permission Cache ──────────────────────────────────────────────────────────


async def get_user_permissions(user_id: UUID) -> set[str]:
    """Kullanıcının permission setini Redis cache üzerinden getirir.

    Cache miss durumunda veritabanından yükler ve cache'e yazar.
    TTL: USER_PERMISSIONS_TTL (15 dakika).
    Rol değişikliğinde cache invalidate edilmelidir.
    """
    from sqlalchemy import select

    from app.db.models.role import RolePermission
    from app.db.models.user import User as UserModel
    from app.db.session import AsyncSessionFactory

    redis = await get_redis_client()
    key = USER_PERMISSIONS_KEY.format(str(user_id))
    cached = await redis.get(key)
    if cached:
        return set(json.loads(cached))

    async with AsyncSessionFactory() as session, session.begin():
        result = await session.execute(
            select(RolePermission.permission)
            .join(UserModel, UserModel.role_id == RolePermission.role_id)
            .where(UserModel.id == user_id)
        )
        perms = set(result.scalars().all())

    await redis.set(key, json.dumps(list(perms)), ex=USER_PERMISSIONS_TTL)
    return perms


# ── Auth Dependencies ─────────────────────────────────────────────────────────


class AuthMethod(StrEnum):
    """Kimlik doğrulama kaynağı."""

    BEARER = "bearer"
    API_KEY = "api_key"


@dataclass(slots=True)
class AuthContext:
    """Authorization kararları için request auth bağlamı."""

    user: User
    auth_method: AuthMethod
    api_key_scopes: set[str] | None = None


async def get_current_auth(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)],
    user_repo: UserRepoDep,
    db: DBDep,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> AuthContext:
    """Bearer token veya X-API-Key header'ından kullanıcıyı çözer.

    JWT access token veya API Key kullanarak kimlik doğrulama yapar.
    Token blacklist kontrolü ve kullanıcı aktiflik durumu doğrulanır.

    Args:
        credentials: HTTP Bearer token credentials.
        user_repo: Kullanıcı repository dependency.
        x_api_key: Opsiyonel API Key header değeri.

    Returns:
        User: Doğrulanmış ve aktif kullanıcı modeli.

    Raises:
        AuthenticationError: Geçerli credentials sağlanmadığında.
        InvalidTokenError: Token türü ACCESS değilse veya blacklist'teyse.
    """
    # API Key auth
    if x_api_key:
        from app.services.api_key import APIKeyService

        svc = APIKeyService(db)
        api_key_obj = await svc.authenticate(x_api_key)
        user = await user_repo.get_by_id(api_key_obj.user_id)
        if not user or not user.is_active:
            raise AuthenticationError("Kullanıcı bulunamadı veya pasif.")
        scopes = {scope for scope in api_key_obj.scopes.split() if scope}
        return AuthContext(user=user, auth_method=AuthMethod.API_KEY, api_key_scopes=scopes)

    # Bearer token auth
    if not credentials:
        raise AuthenticationError("Authorization header veya X-API-Key gerekli.")

    payload = decode_token(credentials.credentials)

    if payload.type != TokenType.ACCESS:
        raise InvalidTokenError("Yanlış token türü.")

    redis = await get_redis_client()
    if await redis.exists(BLACKLIST_KEY.format(payload.jti)):
        raise InvalidTokenError("Token geçersiz kılınmış.")

    user = await user_repo.get_by_id(UUID(payload.sub))
    if not user or not user.is_active:
        raise AuthenticationError("Kullanıcı bulunamadı veya pasif.")

    return AuthContext(user=user, auth_method=AuthMethod.BEARER)


async def get_current_user(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
) -> User:
    """Backward compatible aktif kullanıcı dependency'si."""
    return auth.user


async def get_current_active_auth(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
) -> AuthContext:
    """Aktif auth context'ini döner."""
    return auth


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Aktif kullanıcıyı döner."""
    return current_user


async def get_optional_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)],
    user_repo: UserRepoDep,
    db: DBDep,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> User | None:
    """Opsiyonel kimlik doğrulama dependency'si.

    Credentials sağlanmışsa kullanıcıyı çözer, sağlanmamışsa None döner.
    """
    if not credentials and not x_api_key:
        return None
    auth = await get_current_auth(credentials, user_repo, db, x_api_key)
    return auth.user


async def get_effective_permissions(auth: AuthContext) -> set[str]:
    """Auth kaynağına göre etkili permission setini döner."""
    user_perms = await get_user_permissions(auth.user.id)
    if auth.auth_method is AuthMethod.API_KEY:
        if not auth.api_key_scopes:
            return set()
        return user_perms & auth.api_key_scopes
    return user_perms


def require_permissions_all(*perms: Permission) -> Any:
    """Tüm permission'ları zorunlu kılan dependency factory."""

    async def check(
        auth: Annotated[AuthContext, Depends(get_current_active_auth)],
    ) -> User:
        effective_perms = await get_effective_permissions(auth)
        if not all(p.value in effective_perms for p in perms):
            raise InsufficientPermissionsError(
                f"Bu işlem için gerekli yetki: {', '.join(p.value for p in perms)}"
            )
        return auth.user

    return check


def require_permissions(*perms: Permission) -> Any:
    """Permission tabanlı erişim kontrolü için dependency factory.

    Belirtilen permission'lardan en az birine sahip kullanıcıları
    gerektiren bir dependency fonksiyonu üretir.

    Args:
        *perms: Gerekli Permission enum değerleri (OR mantığı — biri yeterlı).

    Returns:
        Callable: FastAPI dependency olarak kullanılabilecek async fonksiyon.

    Raises:
        InsufficientPermissionsError: Kullanıcı gerekli permission'lardan
            hiçbirine sahip değilse.

    Example:
        >>> @router.get("/users")
        >>> async def list_users(
        ...     _: Annotated[User, Depends(require_permissions(Permission.USERS_READ))]
        ... ): ...
    """

    async def check(
        auth: Annotated[AuthContext, Depends(get_current_active_auth)],
    ) -> User:
        effective_perms = await get_effective_permissions(auth)
        if not any(p.value in effective_perms for p in perms):
            raise InsufficientPermissionsError(
                f"Bu işlem için gerekli yetki: {', '.join(p.value for p in perms)}"
            )
        return auth.user

    return check


# ── Type Aliases ──────────────────────────────────────────────────────────────

CurrentAuthDep = Annotated[AuthContext, Depends(get_current_active_auth)]
"""Aktif auth context dependency type alias."""

CurrentUserDep = Annotated[User, Depends(get_current_active_user)]
"""Aktif kullanıcı dependency type alias."""

OptionalUserDep = Annotated[User | None, Depends(get_optional_current_user)]
"""Opsiyonel kullanıcı dependency type alias."""
