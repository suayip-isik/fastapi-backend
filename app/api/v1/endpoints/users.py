"""
Users endpoint'leri.
Kullanıcı listeleme, güncelleme, silme işlemleri.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import CurrentUserDep, require_permissions
from app.api.dependencies.services import get_audit_service
from app.core.exceptions import InsufficientPermissionsError
from app.core.i18n import t
from app.core.permissions import Permission
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import MessageResponse, PaginatedResponse, calculate_pages
from app.schemas.role import AssignRoleRequest
from app.schemas.user import (
    DeletedUserResponse,
    UpdateUserRequest,
    UserResponse,
    UserStatsResponse,
)
from app.services.audit import AuditService
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["Users"])

# Modül yüklendiğinde bir kez oluşturulur — her request'te tek Redis GET maliyeti.
_UsersReadDep = Annotated[User, Depends(require_permissions(Permission.USERS_READ))]
_UsersWriteDep = Annotated[User, Depends(require_permissions(Permission.USERS_WRITE))]
_UsersDeleteDep = Annotated[User, Depends(require_permissions(Permission.USERS_DELETE))]


def get_user_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> UserService:
    """UserService dependency factory'si."""
    return UserService(db, audit)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]


@router.get(
    "/me", response_model=UserResponse, openapi_extra={"x-audiences": ["admin", "user", "mobile"]}
)
async def get_me(current_user: CurrentUserDep) -> User:
    """Giriş yapmış kullanıcının profil bilgilerini getirir.

    Kimlik doğrulaması yapılmış kullanıcının kendi profil bilgilerini
    döndürür. Token üzerinden kullanıcı kimliği belirlenir.

    Args:
        current_user: JWT token ile doğrulanmış mevcut kullanıcı.

    Returns:
        Kullanıcının profil bilgileri (id, email, ad, rol vb.).
    """
    return current_user


@router.patch(
    "/me", response_model=UserResponse, openapi_extra={"x-audiences": ["admin", "user", "mobile"]}
)
async def update_me(
    data: UpdateUserRequest,
    current_user: CurrentUserDep,
    service: UserServiceDep,
) -> User:
    """Giriş yapmış kullanıcının profil bilgilerini günceller.

    Kullanıcının ad, soyad gibi düzenlenebilir alanlarını günceller.
    Email ve rol gibi hassas alanlar bu endpoint üzerinden değiştirilemez.

    Args:
        data: Güncellenecek profil alanlarını içeren istek verisi.
        current_user: JWT token ile doğrulanmış mevcut kullanıcı.
        service: Kullanıcı işlemlerini yöneten servis.

    Returns:
        Güncellenmiş kullanıcı profil bilgileri.
    """
    return await service.update(current_user.id, data)


@router.get("", response_model=PaginatedResponse[UserResponse])
async def list_users(
    _: _UsersReadDep,
    service: UserServiceDep,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    q: str | None = Query(
        None,
        min_length=1,
        max_length=100,
        description="email, kullanıcı adı veya tam ad içinde arama",
    ),
    role: str | None = Query(None, description="Rol adı filtresi (ör: admin, user)"),
    is_active: bool | None = Query(None, description="Aktiflik durumu filtresi"),
    is_verified: bool | None = Query(None, description="Email doğrulama durumu filtresi"),
) -> PaginatedResponse[UserResponse]:
    """Sistemdeki aktif kullanıcıları filtreler ve sayfalanmış şekilde listeler.

    Sadece admin yetkisine sahip kullanıcılar bu endpoint'e erişebilir.
    Soft-delete ile silinmiş kullanıcılar bu liste dışındadır; bunlar için
    `GET /users/deleted` kullanılmalıdır.

    Args:
        _: Admin yetkisi kontrolü için kullanılan bağımlılık.
        service: Kullanıcı işlemlerini yöneten servis.
        page: Görüntülenecek sayfa numarası (varsayılan: 1).
        size: Sayfa başına kullanıcı sayısı (varsayılan: 20, maks: 100).
        q: Serbest metin arama terimi — email, kullanıcı adı ve tam ad alanlarında aranır.
        role: Filtrelenecek kullanıcı rolü.
        is_active: True = sadece aktif, False = sadece pasif kullanıcılar.
        is_verified: True = sadece doğrulanmış, False = doğrulanmamış kullanıcılar.

    Returns:
        Sayfalanmış kullanıcı listesi (items, total, page, size, pages).
    """
    q = q.strip() or None if q else None
    users, total = await service.search(
        page=page,
        size=size,
        q=q,
        role=role,
        is_active=is_active,
        is_verified=is_verified,
    )
    return PaginatedResponse(
        items=users, total=total, page=page, size=size, pages=calculate_pages(total, size)
    )


@router.get("/stats", response_model=UserStatsResponse)
async def get_user_stats(_: _UsersReadDep, service: UserServiceDep) -> UserStatsResponse:
    """Kullanıcı istatistiklerini döndürür.

    Sistemdeki aktif, pasif ve toplam kullanıcı sayısını döndürür.
    Soft-delete ile silinmiş kullanıcılar sayımlara dahil edilmez.
    Sadece admin yetkisine sahip kullanıcılar bu endpoint'e erişebilir.

    Args:
        _: Admin yetkisi kontrolü için kullanılan bağımlılık.
        service: Kullanıcı işlemlerini yöneten servis.

    Returns:
        Aktif, pasif ve toplam kullanıcı sayılarını içeren istatistik verisi.
    """
    return await service.get_stats()


@router.get("/deleted", response_model=PaginatedResponse[DeletedUserResponse])
async def list_deleted_users(
    _: _UsersReadDep,
    service: UserServiceDep,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    q: str | None = Query(
        None,
        min_length=1,
        max_length=100,
        description="email, kullanıcı adı veya tam ad içinde arama",
    ),
    role: str | None = Query(None, description="Rol adı filtresi (ör: admin, user)"),
    is_active: bool | None = Query(None, description="Silinmeden önceki aktiflik durumu filtresi"),
    is_verified: bool | None = Query(None, description="Email doğrulama durumu filtresi"),
) -> PaginatedResponse[DeletedUserResponse]:
    """Soft-delete ile silinmiş kullanıcıları listeler (admin trash view).

    Sadece admin yetkisine sahip kullanıcılar bu endpoint'e erişebilir.
    Sonuçlar silinme zamanına göre azalan sırada döner (en son silinen önce).
    Silinen kullanıcıları geri yüklemek için `POST /users/{user_id}/restore`
    kullanılmalıdır.

    Args:
        _: Admin yetkisi kontrolü için kullanılan bağımlılık.
        service: Kullanıcı işlemlerini yöneten servis.
        page: Görüntülenecek sayfa numarası (varsayılan: 1).
        size: Sayfa başına kullanıcı sayısı (varsayılan: 20, maks: 100).
        q: Serbest metin arama terimi — email, kullanıcı adı ve tam ad alanlarında aranır.
        role: Filtrelenecek kullanıcı rolü.
        is_active: Silinmeden önceki aktiflik durumu filtresi.
        is_verified: Doğrulama durumu filtresi.

    Returns:
        Sayfalanmış silinen kullanıcı listesi (deleted_at dahil).
    """
    q = q.strip() or None if q else None
    users, total = await service.search_deleted(
        page=page,
        size=size,
        q=q,
        role=role,
        is_active=is_active,
        is_verified=is_verified,
    )
    return PaginatedResponse(
        items=users, total=total, page=page, size=size, pages=calculate_pages(total, size)
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: UUID, _: _UsersReadDep, service: UserServiceDep) -> UserResponse:
    """Belirtilen kullanıcının detaylı bilgilerini getirir.

    Sadece admin yetkisine sahip kullanıcılar bu endpoint'e erişebilir.
    Sonuç önbellekten döndürülebilir (cached).

    Args:
        user_id: Sorgulanacak kullanıcının benzersiz kimliği (UUID).
        _: Admin yetkisi kontrolü için kullanılan bağımlılık.
        service: Kullanıcı işlemlerini yöneten servis.

    Returns:
        Kullanıcının detaylı profil bilgileri.

    Raises:
        NotFoundError: Belirtilen ID'ye sahip kullanıcı bulunamazsa.
    """
    return await service.get_by_id_cached(user_id)


@router.post("/{user_id}/activate", response_model=UserResponse)
async def activate_user(
    user_id: UUID, current_user: _UsersWriteDep, service: UserServiceDep
) -> User:
    """Deaktif edilmiş bir kullanıcıyı tekrar aktif eder.

    Sadece admin yetkisine sahip kullanıcılar bu endpoint'e erişebilir.
    Kullanıcının is_active alanını True olarak günceller ve sisteme
    giriş yapabilmesini sağlar.

    Args:
        user_id: Aktif edilecek kullanıcının benzersiz kimliği (UUID).
        current_user: İşlemi yapan admin kullanıcı.
        service: Kullanıcı işlemlerini yöneten servis.

    Returns:
        Aktif edilmiş kullanıcının güncel profil bilgileri.

    Raises:
        InsufficientPermissionsError: Admin kendi hesabını aktif etmeye çalışırsa.
        NotFoundError: Belirtilen ID'ye sahip kullanıcı bulunamazsa.
    """
    if user_id == current_user.id:
        raise InsufficientPermissionsError(t("error.user.self_action"))
    return await service.activate(user_id)


@router.patch("/{user_id}/role", response_model=UserResponse)
async def assign_user_role(
    user_id: UUID,
    data: AssignRoleRequest,
    current_user: _UsersWriteDep,
    service: UserServiceDep,
) -> User:
    """Kullanıcıya rol atar.

    Sadece admin yetkisine sahip kullanıcılar bu endpoint'e erişebilir.
    Rol değişikliği kullanıcının erişebileceği kaynakları etkiler ve
    permission cache'i invalidate eder.

    Args:
        user_id: Rolü değiştirilecek kullanıcının benzersiz kimliği (UUID).
        data: Atanacak rolün adını içeren istek verisi.
        current_user: İşlemi yapan admin kullanıcı.
        service: Kullanıcı işlemlerini yöneten servis.

    Returns:
        Rol atanmış kullanıcının güncel profil bilgileri.

    Raises:
        InsufficientPermissionsError: Admin kendi rolünü değiştirmeye çalışırsa.
        NotFoundError: Kullanıcı veya rol bulunamazsa.
    """
    if user_id == current_user.id:
        raise InsufficientPermissionsError(t("error.user.self_action"))
    return await service.assign_role(user_id, data.role_name)


@router.post("/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
    user_id: UUID, current_user: _UsersWriteDep, service: UserServiceDep
) -> User:
    """Aktif bir kullanıcıyı deaktif eder.

    Sadece admin yetkisine sahip kullanıcılar bu endpoint'e erişebilir.
    Kullanıcının is_active alanını False olarak günceller. Deaktif
    kullanıcılar sisteme giriş yapamaz ancak verileri korunur.

    Args:
        user_id: Deaktif edilecek kullanıcının benzersiz kimliği (UUID).
        current_user: İşlemi yapan admin kullanıcı.
        service: Kullanıcı işlemlerini yöneten servis.

    Returns:
        Deaktif edilmiş kullanıcının güncel profil bilgileri.

    Raises:
        InsufficientPermissionsError: Admin kendi hesabını deaktif etmeye çalışırsa.
        NotFoundError: Belirtilen ID'ye sahip kullanıcı bulunamazsa.
    """
    if user_id == current_user.id:
        raise InsufficientPermissionsError(t("error.user.self_action"))
    return await service.deactivate(user_id)


@router.delete("/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: UUID, current_user: _UsersDeleteDep, service: UserServiceDep
) -> MessageResponse:
    """Kullanıcıyı soft-delete yöntemiyle siler.

    Sadece admin yetkisine sahip kullanıcılar bu endpoint'e erişebilir.
    Kullanıcı veritabanından kalıcı olarak silinmez, deleted_at alanı
    güncellenir. Silinen kullanıcı restore endpoint'i ile geri yüklenebilir.

    Args:
        user_id: Silinecek kullanıcının benzersiz kimliği (UUID).
        current_user: İşlemi yapan admin kullanıcı.
        service: Kullanıcı işlemlerini yöneten servis.

    Returns:
        İşlem sonucunu bildiren mesaj yanıtı.

    Raises:
        InsufficientPermissionsError: Admin kendi hesabını silmeye çalışırsa.
        NotFoundError: Belirtilen ID'ye sahip kullanıcı bulunamazsa.
    """
    if user_id == current_user.id:
        raise InsufficientPermissionsError(t("error.user.self_action"))
    await service.soft_delete(user_id)
    return MessageResponse(message=t("user.delete.success"))


@router.post("/{user_id}/restore", response_model=UserResponse)
async def restore_user(
    user_id: UUID, current_user: _UsersDeleteDep, service: UserServiceDep
) -> User:
    """Soft-delete ile silinmiş kullanıcıyı geri yükler.

    Sadece admin yetkisine sahip kullanıcılar bu endpoint'e erişebilir.
    Kullanıcının deleted_at alanını temizleyerek hesabı tekrar aktif
    hale getirir. Kalıcı olarak silinmiş kullanıcılar geri yüklenemez.

    Args:
        user_id: Geri yüklenecek kullanıcının benzersiz kimliği (UUID).
        current_user: İşlemi yapan admin kullanıcı.
        service: Kullanıcı işlemlerini yöneten servis.

    Returns:
        Geri yüklenmiş kullanıcının güncel profil bilgileri.

    Raises:
        InsufficientPermissionsError: Admin kendi hesabını geri yüklemeye çalışırsa.
        NotFoundError: Belirtilen ID'ye sahip silinmiş kullanıcı bulunamazsa.
    """
    if user_id == current_user.id:
        raise InsufficientPermissionsError(t("error.user.self_action"))
    return await service.restore(user_id)
