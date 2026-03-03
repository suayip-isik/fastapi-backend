"""
File upload endpoint'leri.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile

from app.api.dependencies.auth import CurrentUserDep
from app.core.config import settings
from app.core.limiter import limiter
from app.schemas.common import MessageResponse
from app.storage.backends import storage

router = APIRouter(prefix="/uploads", tags=["Uploads"])


class UploadResponse(MessageResponse):
    key: str
    url: str


@router.post("", response_model=UploadResponse)
@limiter.limit(settings.RATE_LIMIT_UPLOAD)
async def upload_file(
    request: Request,
    current_user: CurrentUserDep,
    file: UploadFile = File(...),
):
    """Dosya yükle. (Giriş gerekli)"""
    folder = f"users/{current_user.id}"
    key = await storage.upload(file, folder=folder)
    url = await storage.get_url(key)
    return UploadResponse(message="Dosya başarıyla yüklendi.", key=key, url=url)


@router.delete("", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_UPLOAD)
async def delete_file(
    request: Request,
    key: str,
    current_user: CurrentUserDep,
):
    """Dosya sil. (Kullanıcı kendi dosyasını, admin herkesinkini silebilir)"""
    from app.core.exceptions import InsufficientPermissionsError
    from app.db.models.user import UserRole

    is_admin = current_user.role == UserRole.ADMIN
    is_owner = key.startswith(f"users/{str(current_user.id)}/")

    if not is_admin and not is_owner:
        raise InsufficientPermissionsError("Bu dosyayı silme yetkiniz yok.")

    await storage.delete(key)
    return MessageResponse(message="Dosya silindi.")
