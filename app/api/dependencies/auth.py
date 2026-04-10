"""
FastAPI Dependency Injection katmanı.
Tüm ortak bağımlılıklar burada tanımlanır.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Any
from uuid import UUID

from fastapi import Depends, Header, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.infrastructure import RedisAdapter
from app.api.dependencies.infrastructure import PermissionProviderDep, RedisPortDep
from app.api.policies.authz import (
    ensure_permissions_all,
    ensure_permissions_any,
    ensure_surface_access,
)
from app.api.surfaces import Surface
from app.core.exceptions import (
    AuthenticationError,
    InsufficientPermissionsError,
    InvalidTokenError,
)
from app.core.logging import get_logger
from app.core.permissions import Permission
from app.core.security import TokenType, decode_token
from app.db.models.user import AccountType, User
from app.db.repositories.user import UserRepository
from app.db.session import get_db
from app.db.session_provider import get_default_session_factory
from app.services._keys import BLACKLIST_KEY
from app.services.permissions import PermissionCache, PermissionProvider, PermissionQueryService

logger = get_logger(__name__)

# ── Security Scheme ───────────────────────────────────────────────────────────

bearer_scheme = HTTPBearer(auto_error=False)

# ── DB Dependency ─────────────────────────────────────────────────────────────

DBDep = Annotated[AsyncSession, Depends(get_db)]

# ── Repository Dependencies ───────────────────────────────────────────────────


def get_user_repository(db: DBDep) -> UserRepository:
    return UserRepository(db)


UserRepoDep = Annotated[UserRepository, Depends(get_user_repository)]

# ── Permission Cache ──────────────────────────────────────────────────────────


async def get_user_permissions(
    user_id: UUID,
    provider: PermissionProvider | None = None,
) -> set[str]:
    """Kullanıcının permission setini Redis cache üzerinden getirir.

    Cache miss durumunda veritabanından yükler ve cache'e yazar.
    TTL: USER_PERMISSIONS_TTL (15 dakika).
    Rol değişikliğinde cache invalidate edilmelidir.
    """
    resolved_provider = provider or _build_permission_provider(RedisAdapter())
    return await resolved_provider.get_permissions(user_id)


def _build_permission_provider(redis: object) -> PermissionProvider:
    return PermissionProvider(
        query_service=PermissionQueryService(get_default_session_factory()),
        cache=PermissionCache(redis),  # type: ignore[arg-type]
    )


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
    redis: RedisPortDep,
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
    redis: RedisPortDep,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> User | None:
    """Opsiyonel kimlik doğrulama dependency'si.

    Credentials sağlanmışsa kullanıcıyı çözer, sağlanmamışsa None döner.
    """
    if not credentials and not x_api_key:
        return None
    auth = await get_current_auth(credentials, user_repo, db, redis, x_api_key)
    return auth.user


async def get_effective_permissions(
    auth: AuthContext,
    permission_provider: PermissionProvider | None = None,
) -> set[str]:
    """Auth kaynağına göre etkili permission setini döner."""
    resolved_provider = permission_provider or _build_permission_provider(RedisAdapter())
    try:
        user_perms = await resolved_provider.get_permissions(auth.user.id)
    except (RedisError, SQLAlchemyError, OSError, ValueError, TypeError):
        logger.warning("permission_resolution_failed", user_id=str(auth.user.id), exc_info=True)
        return set()

    if auth.auth_method is AuthMethod.API_KEY:
        if not auth.api_key_scopes:
            return set()
        return user_perms & auth.api_key_scopes
    return user_perms


def require_account_type(*allowed: AccountType) -> Any:
    """Belirli account_type değerlerinden birini zorunlu kılar."""

    allowed_values = {account_type.value for account_type in allowed}

    async def check(
        auth: Annotated[AuthContext, Depends(get_current_active_auth)],
    ) -> User:
        if auth.user.account_type not in allowed_values:
            raise InsufficientPermissionsError("Bu kullanıcı türü bu kaynağa erişemez.")
        return auth.user

    return check


def require_surface_access(surface: Surface) -> Any:
    """Surface bazlı erişim kontrolü yapar."""

    if surface is Surface.SHARED:

        async def allow_shared(
            auth: Annotated[AuthContext, Depends(get_current_active_auth)],
        ) -> User:
            return auth.user

        return allow_shared

    async def check(
        auth: Annotated[AuthContext, Depends(get_current_active_auth)],
    ) -> User:
        ensure_surface_access(auth.user.account_type, surface)
        return auth.user

    return check


def require_permissions_all(*perms: Permission) -> Any:
    """Tüm permission'ları zorunlu kılan dependency factory."""

    async def check(
        auth: Annotated[AuthContext, Depends(get_current_active_auth)],
        permission_provider: PermissionProviderDep,
    ) -> User:
        effective_perms = await get_effective_permissions(auth, permission_provider)
        ensure_permissions_all(effective_perms, *perms)
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
        permission_provider: PermissionProviderDep,
    ) -> User:
        effective_perms = await get_effective_permissions(auth, permission_provider)
        ensure_permissions_any(effective_perms, *perms)
        return auth.user

    return check


# ── Type Aliases ──────────────────────────────────────────────────────────────

CurrentAuthDep = Annotated[AuthContext, Depends(get_current_active_auth)]
"""Aktif auth context dependency type alias."""

CurrentUserDep = Annotated[User, Depends(get_current_active_user)]
"""Aktif kullanıcı dependency type alias."""

OptionalUserDep = Annotated[User | None, Depends(get_optional_current_user)]
"""Opsiyonel kullanıcı dependency type alias."""
