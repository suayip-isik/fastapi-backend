"""
Storage abstraction layer.
Interface Segregation Principle: StorageBackend abstract class ile kontrat tanımı.
Yeni storage provider eklemek için sadece yeni bir class yazılır.
"""
from __future__ import annotations

import mimetypes
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

import aioboto3
from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import FileTooLargeError, InvalidFileTypeError, StorageError
from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Interface ─────────────────────────────────────────────────────────────────

class StorageBackend(ABC):
    @abstractmethod
    async def upload(self, file: UploadFile, folder: str = "") -> str:
        """Dosyayı yükle, public URL döndür."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Dosyayı sil."""
        ...

    @abstractmethod
    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        """Presigned URL üret."""
        ...


# ── Validators ────────────────────────────────────────────────────────────────

async def validate_upload(file: UploadFile) -> bytes:
    """Boyut ve MIME type doğrula, bytes döndür."""
    content = await file.read()

    if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise FileTooLargeError(
            f"Maksimum dosya boyutu {settings.MAX_UPLOAD_SIZE_MB}MB."
        )

    content_type = file.content_type or ""
    if content_type not in settings.ALLOWED_UPLOAD_TYPES:
        raise InvalidFileTypeError(
            f"Desteklenmeyen dosya türü: {content_type}. "
            f"İzin verilenler: {', '.join(settings.ALLOWED_UPLOAD_TYPES)}"
        )

    return content


def _generate_key(folder: str, filename: str) -> str:
    """Benzersiz dosya anahtarı üret."""
    ext = Path(filename).suffix.lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"
    return f"{folder.strip('/')}/{unique_name}" if folder else unique_name


# ── S3 / MinIO Backend ────────────────────────────────────────────────────────

class S3StorageBackend(StorageBackend):
    """AWS S3 ve MinIO için ortak implementasyon."""

    def __init__(self) -> None:
        self._session = aioboto3.Session(
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
        )
        self._endpoint = settings.S3_ENDPOINT_URL or None
        self._bucket = settings.S3_BUCKET_NAME

    async def upload(self, file: UploadFile, folder: str = "") -> str:
        content = await validate_upload(file)
        key = _generate_key(folder, file.filename or "upload")

        try:
            async with self._session.client("s3", endpoint_url=self._endpoint) as s3:
                await s3.put_object(
                    Bucket=self._bucket,
                    Key=key,
                    Body=content,
                    ContentType=file.content_type or "application/octet-stream",
                )
            logger.info("file_uploaded", key=key, size=len(content))
            return key
        except Exception as e:
            logger.error("upload_failed", error=str(e))
            raise StorageError(f"Yükleme başarısız: {e}")

    async def delete(self, key: str) -> None:
        try:
            async with self._session.client("s3", endpoint_url=self._endpoint) as s3:
                await s3.delete_object(Bucket=self._bucket, Key=key)
            logger.info("file_deleted", key=key)
        except Exception as e:
            logger.error("delete_failed", key=key, error=str(e))
            raise StorageError(f"Silme başarısız: {e}")

    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        try:
            async with self._session.client("s3", endpoint_url=self._endpoint) as s3:
                url = await s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self._bucket, "Key": key},
                    ExpiresIn=expires_in,
                )
            return url
        except Exception as e:
            raise StorageError(f"URL üretimi başarısız: {e}")


# ── Factory ───────────────────────────────────────────────────────────────────

def get_storage() -> StorageBackend:
    """Storage backend'i config'e göre döndür."""
    backend = settings.STORAGE_BACKEND.lower()
    if backend in ("s3", "minio"):
        return S3StorageBackend()
    raise ValueError(f"Bilinmeyen storage backend: {backend}")


# Singleton instance
storage: StorageBackend = get_storage()
