"""
File upload endpoint'leri.
"""

from fastapi import APIRouter, File, Request, UploadFile

from app.api.dependencies.auth import CurrentAuthDep, get_effective_permissions
from app.api.dependencies.services import AuditServiceDep
from app.core.config import settings
from app.core.exceptions import InvalidFileTypeError
from app.core.limiter import limiter
from app.db.models.audit_log import AuditAction
from app.schemas.common import MessageResponse
from app.storage.backends import storage

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
        POST /api/v1/uploads
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
    if file.content_type not in settings.ALLOWED_UPLOAD_TYPES:
        raise InvalidFileTypeError(
            f"'{file.content_type}' tipi desteklenmiyor. "
            f"İzin verilenler: {', '.join(settings.ALLOWED_UPLOAD_TYPES)}"
        )
    folder = f"users/{current_user.user.id}"
    key = await storage.upload(file, folder=folder)
    url = await storage.get_url(key)
    await audit.log(
        AuditAction.FILE_UPLOADED,
        user_id=current_user.user.id,
        extra={"key": key, "filename": file.filename},
    )
    return UploadResponse(message="Dosya başarıyla yüklendi.", key=key, url=url)


@router.delete("", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_UPLOAD)
async def delete_file(
    request: Request,
    key: str,
    current_user: CurrentAuthDep,
    audit: AuditServiceDep,
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
        DELETE /api/v1/uploads?key=users/123/file.pdf
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
    from app.core.exceptions import InsufficientPermissionsError
    from app.core.permissions import Permission

    is_owner = key.startswith(f"users/{current_user.user.id!s}/")
    effective_perms = await get_effective_permissions(current_user)
    can_delete_any = Permission.ADMIN_ACCESS.value in effective_perms

    if not can_delete_any and not is_owner:
        raise InsufficientPermissionsError("Bu dosyayı silme yetkiniz yok.")

    await storage.delete(key)
    await audit.log(
        AuditAction.FILE_DELETED,
        user_id=current_user.user.id,
        extra={"key": key},
    )
    return MessageResponse(message="Dosya silindi.")
