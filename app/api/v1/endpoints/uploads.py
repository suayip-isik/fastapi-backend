"""
File upload endpoint'leri.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile

from app.api.dependencies.auth import CurrentUserDep
from app.core.config import settings
from app.core.limiter import limiter
from app.db.models.audit_log import AuditAction
from app.schemas.common import MessageResponse
from app.services.audit import AuditService
from app.storage.backends import storage

router = APIRouter(prefix="/uploads", tags=["Uploads"])


class UploadResponse(MessageResponse):
    key: str
    url: str


def get_audit_service() -> AuditService:
    return AuditService()


AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]


@router.post("", response_model=UploadResponse)
@limiter.limit(settings.RATE_LIMIT_UPLOAD)
async def upload_file(
    request: Request,
    current_user: CurrentUserDep,
    audit: AuditServiceDep,
    file: UploadFile = File(...),
):
    """Dosya yükle. (Giriş gerekli)"""
    folder = f"users/{current_user.id}"
    key = await storage.upload(file, folder=folder)
    url = await storage.get_url(key)
    await audit.log(
        AuditAction.FILE_UPLOADED,
        user_id=current_user.id,
        extra={"key": key, "filename": file.filename},
    )
    return UploadResponse(message="Dosya başarıyla yüklendi.", key=key, url=url)


@router.delete("", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_UPLOAD)
async def delete_file(
    request: Request,
    key: str,
    current_user: CurrentUserDep,
    audit: AuditServiceDep,
):
    """Dosya sil. (Kullanıcı kendi dosyasını, admin herkesinkini silebilir)"""
    from app.core.exceptions import InsufficientPermissionsError
    from app.db.models.user import UserRole

    is_admin = current_user.role == UserRole.ADMIN
    is_owner = key.startswith(f"users/{current_user.id!s}/")

    if not is_admin and not is_owner:
        raise InsufficientPermissionsError("Bu dosyayı silme yetkiniz yok.")

    await storage.delete(key)
    await audit.log(
        AuditAction.FILE_DELETED,
        user_id=current_user.id,
        extra={"key": key},
    )
    return MessageResponse(message="Dosya silindi.")
