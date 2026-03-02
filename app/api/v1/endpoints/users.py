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
from app.db.models.user import UserRole
from app.db.session import get_db
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.user import UpdateUserRequest, UserResponse
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["Users"])


def get_user_service(db: Annotated[AsyncSession, Depends(get_db)]) -> UserService:
    return UserService(db)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUserDep):
    """Giriş yapmış kullanıcının profili."""
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: UpdateUserRequest,
    current_user: CurrentUserDep,
    service: UserServiceDep,
):
    """Giriş yapmış kullanıcının profilini güncelle."""
    return await service.update(current_user.id, data)


@router.get("", response_model=PaginatedResponse[UserResponse])
async def list_users(
    _: AdminDep,
    service: UserServiceDep,
    page: int = 1,
    size: int = 20,
):
    """Tüm kullanıcıları listele. (Sadece Admin)"""
    users, total = await service.get_all(page=page, size=size)
    pages = (total + size - 1) // size
    return PaginatedResponse(items=users, total=total, page=page, size=size, pages=pages)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: UUID, _: AdminDep, service: UserServiceDep):
    """Belirli bir kullanıcıyı getir. (Sadece Admin)"""
    return await service.get_by_id(user_id)


@router.delete("/{user_id}", response_model=MessageResponse)
async def deactivate_user(user_id: UUID, _: AdminDep, service: UserServiceDep):
    """Kullanıcıyı deaktif et. (Sadece Admin)"""
    await service.deactivate(user_id)
    return MessageResponse(message="Kullanıcı deaktif edildi.")
