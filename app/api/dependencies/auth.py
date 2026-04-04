"""
FastAPI Dependency Injection katmanı.
Tüm ortak bağımlılıklar burada tanımlanır.
"""

from __future__ import annotations

from typing import Annotated, Any
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
from app.db.models.user import User, UserRole
from app.db.repositories.user import UserRepository
from app.db.session import get_db
from app.services._keys import BLACKLIST_KEY

# ── Security Scheme ───────────────────────────────────────────────────────────

bearer_scheme = HTTPBearer(auto_error=False)

# ── DB Dependency ─────────────────────────────────────────────────────────────

DBDep = Annotated[AsyncSession, Depends(get_db)]

# ── Repository Dependencies ───────────────────────────────────────────────────


def get_user_repository(db: DBDep) -> UserRepository:
    """UserRepository instance döner (dependency injection).

    Database session dependency'sini alarak UserRepository
    instance'ı oluşturur. FastAPI dependency injection sistemi
    tarafından otomatik çözümlenir.

    Args:
        db: Database session dependency (DBDep = Annotated[AsyncSession, Depends(get_db)])

    Returns:
        UserRepository: Kullanıcı veritabanı işlemleri için repository instance

    Example:
        >>> @router.get("/users/{user_id}")
        >>> async def get_user(
        ...     user_id: UUID,
        ...     user_repo: UserRepoDep
        ... ):
        ...     return await user_repo.get_by_id(user_id)
    """
    return UserRepository(db)


UserRepoDep = Annotated[UserRepository, Depends(get_user_repository)]

# ── Auth Dependencies ─────────────────────────────────────────────────────────


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)],
    user_repo: UserRepoDep,
    db: DBDep,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> User:
    """Bearer token veya X-API-Key header'ından kullanıcıyı çözer.

    JWT access token veya API Key kullanarak kimlik doğrulama yapar.
    Token blacklist kontrolü ve kullanıcı aktiflik durumu doğrulanır.

    Args:
        credentials: HTTP Bearer token credentials. Authorization header'ından
            otomatik çözümlenir. None ise X-API-Key kontrol edilir.
        user_repo: Kullanıcı repository dependency. Veritabanı sorguları için.
        x_api_key: Opsiyonel API Key header değeri. Bearer token yoksa kullanılır.

    Returns:
        User: Doğrulanmış ve aktif kullanıcı modeli.

    Raises:
        AuthenticationError: Geçerli credentials sağlanmadığında veya
            kullanıcı bulunamadığında/pasif olduğunda.
        InvalidTokenError: Token türü ACCESS değilse veya token
            blacklist'te ise.

    Example:
        >>> @router.get("/me")
        >>> async def get_me(
        ...     user: Annotated[User, Depends(get_current_user)]
        ... ) -> UserResponse:
        ...     return user
    """
    # API Key auth
    if x_api_key:
        from app.services.api_key import APIKeyService

        svc = APIKeyService(db)
        api_key_obj = await svc.authenticate(x_api_key)
        user = await user_repo.get_by_id(api_key_obj.user_id)
        if not user or not user.is_active:
            raise AuthenticationError("Kullanıcı bulunamadı veya pasif.")
        return user

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

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Aktif ve doğrulanmış kullanıcıyı döner.

    get_current_user üzerine ince bir sarmalayıcı. Endpoint'lerin büyük
    çoğunluğu bu dependency'yi kullanır. İleride email doğrulama gibi
    ek kontroller eklenebilir.

    Args:
        current_user: get_current_user dependency'sinden çözümlenen kullanıcı.

    Returns:
        User: Aktif ve doğrulanmış kullanıcı modeli.

    Example:
        >>> @router.put("/profile")
        >>> async def update_profile(
        ...     user: CurrentUserDep,
        ...     data: ProfileUpdate
        ... ) -> UserResponse:
        ...     # user aktif ve doğrulanmış
        ...     return await service.update(user, data)
    """
    return current_user


async def get_optional_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)],
    user_repo: UserRepoDep,
    db: DBDep,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> User | None:
    """Opsiyonel kimlik doğrulama dependency'si.

    Credentials sağlanmışsa kullanıcıyı çözer, sağlanmamışsa None döner.
    Public endpoint'lerde opsiyonel auth için kullanılır (örn: giriş yapmış
    kullanıcılara farklı içerik gösterme).

    Args:
        credentials: HTTP Bearer token credentials. Opsiyonel.
        user_repo: Kullanıcı repository dependency.
        x_api_key: Opsiyonel API Key header değeri.

    Returns:
        User | None: Doğrulanmış kullanıcı veya credentials yoksa None.

    Raises:
        InvalidTokenError: Credentials sağlanmış ama geçersizse.
        AuthenticationError: Credentials sağlanmış ama kullanıcı bulunamadıysa.

    Example:
        >>> @router.get("/posts")
        >>> async def list_posts(
        ...     user: OptionalUserDep
        ... ) -> list[Post]:
        ...     if user:
        ...         return await service.list_for_user(user)
        ...     return await service.list_public()
    """
    if not credentials and not x_api_key:
        return None
    return await get_current_user(credentials, user_repo, db, x_api_key)


def require_roles(*roles: UserRole) -> Any:
    """Rol tabanlı erişim kontrolü için dependency factory.

    Belirtilen rollerden birine sahip kullanıcıları gerektiren
    bir dependency fonksiyonu üretir. RBAC implementasyonu için kullanılır.

    Args:
        *roles: İzin verilen UserRole enum değerleri. Kullanıcının
            bu rollerden en az birine sahip olması gerekir.

    Returns:
        Callable: FastAPI dependency olarak kullanılabilecek async fonksiyon.
            Başarılı olursa User döner.

    Raises:
        InsufficientPermissionsError: Kullanıcı gerekli rollerden
            hiçbirine sahip değilse (dependency içinde).

    Example:
        >>> @router.delete("/users/{user_id}")
        >>> async def delete_user(
        ...     user_id: UUID,
        ...     admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))]
        ... ) -> None:
        ...     # Sadece ADMIN rolü erişebilir
        ...     await service.delete(user_id)

        >>> # Birden fazla rol için:
        >>> @router.get("/reports")
        >>> async def get_reports(
        ...     user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.MODERATOR))]
        ... ) -> list[Report]:
        ...     return await service.list_reports()
    """

    async def check_role(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        """Kullanıcının gerekli rollerden en az birine sahip olduğunu doğrular.

        require_roles factory'si tarafından oluşturulan iç dependency fonksiyonu.
        Dış scope'taki `roles` değişkenini yakalar (closure).

        Args:
            current_user: get_current_active_user dependency'sinden çözümlenen
                doğrulanmış aktif kullanıcı.

        Returns:
            User: Rol kontrolünü geçen kullanıcı.

        Raises:
            InsufficientPermissionsError: Kullanıcının rolü, izin verilen
                roller arasında yer almıyorsa.
        """
        if current_user.role not in roles:
            raise InsufficientPermissionsError(
                f"Bu işlem için gerekli rol: {', '.join(r.value for r in roles)}"
            )
        return current_user

    return check_role


# ── Type Aliases ──────────────────────────────────────────────────────────────

CurrentUserDep = Annotated[User, Depends(get_current_active_user)]
"""Aktif kullanıcı dependency type alias.

Endpoint parametrelerinde `user: CurrentUserDep` şeklinde kullanılır.
Otomatik olarak JWT/API Key doğrulaması yapar.

Example:
    >>> @router.get("/me")
    >>> async def get_me(user: CurrentUserDep) -> UserResponse:
    ...     return user
"""

AdminDep = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
"""Admin rolü gerektiren dependency type alias.

Sadece ADMIN rolüne sahip kullanıcıların erişebileceği endpoint'ler için.

Example:
    >>> @router.delete("/users/{user_id}")
    >>> async def delete_user(admin: AdminDep, user_id: UUID) -> None:
    ...     await service.delete(user_id)
"""

OptionalUserDep = Annotated[User | None, Depends(get_optional_current_user)]
"""Opsiyonel kullanıcı dependency type alias.

Public endpoint'lerde opsiyonel auth için kullanılır.
Credentials yoksa None döner, varsa doğrulama yapar.

Example:
    >>> @router.get("/feed")
    >>> async def get_feed(user: OptionalUserDep) -> FeedResponse:
    ...     if user:
    ...         return await service.personalized_feed(user)
    ...     return await service.public_feed()
"""
