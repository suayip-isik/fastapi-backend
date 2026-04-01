"""
Users endpoint'leri.
Kullanıcı listeleme, güncelleme, silme işlemleri.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import AdminDep, CurrentUserDep
from app.core.exceptions import InsufficientPermissionsError
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.user import ChangeRoleRequest, UpdateUserRequest, UserResponse
from app.services.audit import AuditService
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["Users"])


def get_audit_service() -> AuditService:
    return AuditService()


def get_user_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> UserService:
    return UserService(db, audit)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUserDep) -> User:
    """Giris yapmis kullanicinin profili."""
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: UpdateUserRequest,
    current_user: CurrentUserDep,
    service: UserServiceDep,
) -> User:
    """Giris yapmis kullanicinin profilini guncelle."""
    return await service.update(current_user.id, data)


@router.get("", response_model=PaginatedResponse[UserResponse])
async def list_users(
    _: AdminDep,
    service: UserServiceDep,
    page: int = 1,
    size: int = 20,
) -> PaginatedResponse[UserResponse]:
    """Tum kullanicilari listele. (Sadece Admin)"""
    users, total = await service.get_all(page=page, size=size)
    pages = (total + size - 1) // size
    return PaginatedResponse(items=users, total=total, page=page, size=size, pages=pages)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: UUID, _: AdminDep, service: UserServiceDep) -> User:
    """Belirli bir kullaniciyi getir. (Sadece Admin)"""
    return await service.get_by_id(user_id)


@router.post("/{user_id}/activate", response_model=UserResponse)
async def activate_user(user_id: UUID, current_user: AdminDep, service: UserServiceDep) -> User:
    """Kullaniciyi aktif et. (Sadece Admin)"""
    if user_id == current_user.id:
        raise InsufficientPermissionsError("Kendi hesabınız üzerinde bu işlemi yapamazsınız.")
    return await service.activate(user_id)


@router.patch("/{user_id}/role", response_model=UserResponse)
async def change_user_role(
    user_id: UUID,
    data: ChangeRoleRequest,
    current_user: AdminDep,
    service: UserServiceDep,
) -> User:
    """Kullanicinin rolunu degistir. (Sadece Admin)"""
    if user_id == current_user.id:
        raise InsufficientPermissionsError("Kendi hesabınız üzerinde bu işlemi yapamazsınız.")
    return await service.change_role(user_id, data.role)


@router.delete("/{user_id}", response_model=MessageResponse)
async def deactivate_user(
    user_id: UUID, current_user: AdminDep, service: UserServiceDep
) -> MessageResponse:
    """Kullaniciyi deaktif et. (Sadece Admin)"""
    if user_id == current_user.id:
        raise InsufficientPermissionsError("Kendi hesabınız üzerinde bu işlemi yapamazsınız.")
    await service.deactivate(user_id)
    return MessageResponse(message="Kullanici deaktif edildi.")
