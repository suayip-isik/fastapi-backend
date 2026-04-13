"""
File upload endpoint'leri.
"""

from fastapi import APIRouter, File, Request, UploadFile

from app.api.dependencies.auth import CurrentAuthDep, get_effective_permissions
from app.api.dependencies.infrastructure import StoragePortDep
from app.api.dependencies.services import AuditServiceDep
from app.api.policies.permissions import can_delete_any_uploaded_file
from app.core.config import settings
from app.core.exceptions import InsufficientPermissionsError, InvalidFileTypeError
from app.core.i18n import t
from app.core.limiter import limiter
from app.core.permissions import Permission
from app.db.models.audit_log import AuditAction
from app.schemas.common import MessageResponse

router = APIRouter(prefix="/uploads", tags=["Uploads"])


class UploadResponse(MessageResponse):
    """UploadResponse sınıfı."""

    key: str
    url: str


@router.post("", response_model=UploadResponse)
@limiter.limit(settings.RATE_LIMIT_UPLOAD)
async def upload_file(
    request: Request,
    current_user: CurrentAuthDep,
    audit: AuditServiceDep,
    storage: StoragePortDep,
    file: UploadFile = File(...),
) -> UploadResponse:
    """Dosya yükler (authenticated).

    Kullanıcı dosya upload edebilir. Yüklenen dosya kullanıcının kendi
    klasörüne (users/{user_id}/) kaydedilir. Upload işlemi rate limit'e
    tabidir ve audit log kaydı oluşturur.

    Args:
        request: FastAPI Request objesi (rate limiting için)
        current_user: Authentication dependency - aktif kullanıcı
        audit: Audit service dependency - log kaydı için
        file: Yüklenecek dosya (multipart/form-data)

    Returns:
        UploadResponse: message, file_key ve public URL bilgileri

    Raises:
        RateLimitExceeded: Rate limit aşıldığında
        StorageError: Upload başarısız olursa
        UnauthorizedError: Kullanıcı authenticate değilse

    Example:
        POST /api/v1/shared/uploads
        Content-Type: multipart/form-data
        Authorization: Bearer <token>

        file: <binary>

        Response:
        {
            "message": "Dosya başarıyla yüklendi.",
            "key": "users/123/abc-def-document.pdf",
            "url": "https://storage.../users/123/abc-def-document.pdf"
        }

    Note:
        - Dosyalar otomatik olarak users/{user_id}/ klasörüne yüklenir
        - Rate limit: RATE_LIMIT_UPLOAD (settings'den)
        - Audit log: FILE_UPLOADED action ile kaydedilir
        - File key ve filename audit log'a eklenir
    """
    effective_perms = await get_effective_permissions(current_user)
    if Permission.UPLOADS_CREATE_OWN.value not in effective_perms:
        raise InsufficientPermissionsError(t("error.auth.insufficient_permissions"))
    if file.content_type not in settings.ALLOWED_UPLOAD_TYPES:
        raise InvalidFileTypeError(
            t(
                "error.upload.invalid_file_type",
                content_type=file.content_type,
                allowed=", ".join(settings.ALLOWED_UPLOAD_TYPES),
            )
        )
    folder = f"users/{current_user.user.id}"
    key = await storage.upload(file, folder=folder)
    url = await storage.get_url(key)
    await audit.log(
        AuditAction.FILE_UPLOADED,
        user_id=current_user.user.id,
        extra={"key": key, "filename": file.filename},
    )
    return UploadResponse(message=t("upload.upload.success"), key=key, url=url)


@router.delete("", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_UPLOAD)
async def delete_file(
    request: Request,
    key: str,
    current_user: CurrentAuthDep,
    audit: AuditServiceDep,
    storage: StoragePortDep,
) -> MessageResponse:
    """Dosya siler (authenticated + permission check).

    Kullanıcı kendi dosyalarını silebilir (users/{user_id}/ altındaki).
    Admin rolündeki kullanıcılar tüm dosyaları silebilir. Silme işlemi
    rate limit'e tabidir ve audit log kaydı oluşturur.

    Args:
        request: FastAPI Request objesi (rate limiting için)
        key: Silinecek dosyanın storage key'i (örn: "users/123/file.pdf")
        current_user: Authentication dependency - aktif kullanıcı
        audit: Audit service dependency - log kaydı için

    Returns:
        MessageResponse: Başarı mesajı

    Raises:
        InsufficientPermissionsError: Kullanıcı dosya sahibi veya admin değilse
        RateLimitExceeded: Rate limit aşıldığında
        StorageError: Silme işlemi başarısız olursa
        UnauthorizedError: Kullanıcı authenticate değilse

    Example:
        DELETE /api/v1/shared/uploads?key=users/123/file.pdf
        Authorization: Bearer <token>

        Response:
        {
            "message": "Dosya silindi."
        }

    Note:
        - Kullanıcılar sadece kendi klasörlerindeki dosyaları silebilir
        - Admin rolündeki kullanıcılar tüm dosyaları silebilir
        - Ownership kontrolü key prefix'ine göre yapılır (users/{user_id}/)
        - Rate limit: RATE_LIMIT_UPLOAD (settings'den)
        - Audit log: FILE_DELETED action ile kaydedilir
    """
    # Path traversal ve geçersiz key kontrolü
    normalised_key = key.strip().lstrip("/")
    if ".." in normalised_key or normalised_key != key.strip().lstrip("/"):
        raise InsufficientPermissionsError(t("error.upload.invalid_key"))

    user_prefix = f"users/{current_user.user.id!s}/"
    is_owner = normalised_key.startswith(user_prefix) and len(normalised_key) > len(user_prefix)
    effective_perms = await get_effective_permissions(current_user)
    can_delete_any = can_delete_any_uploaded_file(
        current_user.user.surface,
        effective_perms,
    )
    can_delete_own = Permission.UPLOADS_DELETE_OWN.value in effective_perms

    if not can_delete_any and not (can_delete_own and is_owner):
        raise InsufficientPermissionsError(t("error.upload.delete_forbidden"))

    await storage.delete(key)
    await audit.log(
        AuditAction.FILE_DELETED,
        user_id=current_user.user.id,
        extra={"key": key},
    )
    return MessageResponse(message=t("upload.delete.success"))
