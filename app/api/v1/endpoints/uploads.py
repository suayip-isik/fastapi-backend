"""
File upload endpoint'leri.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, UploadFile, File
from typing import Annotated

from app.api.dependencies.auth import CurrentUserDep
from app.storage.backends import storage
from app.schemas.common import MessageResponse

router = APIRouter(prefix="/uploads", tags=["Uploads"])


class UploadResponse(MessageResponse):
    key: str
    url: str


@router.post("", response_model=UploadResponse)
async def upload_file(
    current_user: CurrentUserDep,
    file: UploadFile = File(...),
):
    """Dosya yükle. (Giriş gerekli)"""
    folder = f"users/{current_user.id}"
    key = await storage.upload(file, folder=folder)
    url = await storage.get_url(key)
    return UploadResponse(message="Dosya başarıyla yüklendi.", key=key, url=url)


@router.delete("", response_model=MessageResponse)
async def delete_file(
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
