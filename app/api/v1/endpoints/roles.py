"""Roles endpoint'leri — rol ve permission yönetimi."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_permissions
from app.api.dependencies.services import get_audit_service
from app.core.permissions import Permission
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import MessageResponse
from app.schemas.role import CreateRoleRequest, RoleResponse, UpdateRoleRequest
from app.services.audit import AuditService
from app.services.role import RoleService

router = APIRouter(prefix="/roles", tags=["Roles"])

_RolesReadDep = Annotated[User, Depends(require_permissions(Permission.ROLES_READ))]
_RolesWriteDep = Annotated[User, Depends(require_permissions(Permission.ROLES_WRITE))]


def get_role_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> RoleService:
    return RoleService(db, audit)


RoleServiceDep = Annotated[RoleService, Depends(get_role_service)]


@router.get("", response_model=list[RoleResponse])
async def list_roles(_: _RolesReadDep, service: RoleServiceDep) -> list[RoleResponse]:
    """Sistemdeki tüm rolleri listeler.

    Sistem rolleri ve özel roller dahil tüm roller alfabetik sırayla
    döner. Her rolün permission listesi de response'a dahil edilir.

    Args:
        _: Admin yetkisi kontrolü.
        service: Rol işlemlerini yöneten servis.

    Returns:
        Tüm rollerin listesi (permission seti dahil).
    """
    roles = await service.list_roles()
    return [RoleResponse.from_role(r) for r in roles]


@router.post("", response_model=RoleResponse, status_code=201)
async def create_role(
    data: CreateRoleRequest, _: _RolesWriteDep, service: RoleServiceDep
) -> RoleResponse:
    """Yeni özel rol oluşturur.

    Sistem rolleri (admin, user, moderator) bu endpoint ile
    oluşturulamaz. Rol adı küçük harf, rakam ve alt çizgiden
    oluşmalıdır (ör: "accountant", "warehouse_manager").

    Args:
        data: Rol adı, açıklaması ve başlangıç permission listesi.
        _: Admin yetkisi kontrolü.
        service: Rol işlemlerini yöneten servis.

    Returns:
        Oluşturulan rolün bilgileri.

    Raises:
        AlreadyExistsError: Aynı isimde rol mevcutsa.
    """
    perms = [p.value for p in data.permissions]
    role = await service.create(data.name, data.description, perms)
    return RoleResponse.from_role(role)


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(role_id: UUID, _: _RolesReadDep, service: RoleServiceDep) -> RoleResponse:
    """Belirtilen rolün detaylarını getirir.

    Args:
        role_id: Sorgulanacak rolün UUID'si.
        _: Admin yetkisi kontrolü.
        service: Rol işlemlerini yöneten servis.

    Returns:
        Rol bilgileri ve permission listesi.

    Raises:
        NotFoundError: Rol bulunamazsa.
    """
    role = await service.get_by_id(role_id)
    return RoleResponse.from_role(role)


@router.patch("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: UUID, data: UpdateRoleRequest, _: _RolesWriteDep, service: RoleServiceDep
) -> RoleResponse:
    """Rol açıklamasını ve/veya permission setini günceller.

    Sistem rollerinin permission seti değiştirilemez, yalnızca
    açıklaması güncellenebilir.

    Args:
        role_id: Güncellenecek rolün UUID'si.
        data: Yeni açıklama ve/veya permission listesi.
        _: Admin yetkisi kontrolü.
        service: Rol işlemlerini yöneten servis.

    Returns:
        Güncellenmiş rol bilgileri.

    Raises:
        NotFoundError: Rol bulunamazsa.
        BusinessRuleError: Sistem rolünün permission seti değiştirilmeye çalışılırsa.
    """
    perms = [p.value for p in data.permissions] if data.permissions is not None else None
    role = await service.update(role_id, data.description, perms)
    return RoleResponse.from_role(role)


@router.delete("/{role_id}", response_model=MessageResponse)
async def delete_role(role_id: UUID, _: _RolesWriteDep, service: RoleServiceDep) -> MessageResponse:
    """Özel rolü siler.

    Sistem rolleri (admin, user, moderator) silinemez.

    Args:
        role_id: Silinecek rolün UUID'si.
        _: Admin yetkisi kontrolü.
        service: Rol işlemlerini yöneten servis.

    Returns:
        Silme işlemi sonuç mesajı.

    Raises:
        NotFoundError: Rol bulunamazsa.
        BusinessRuleError: Sistem rolü silinmeye çalışılırsa.
    """
    await service.delete(role_id)
    return MessageResponse(message="Rol silindi.")
