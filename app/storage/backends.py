"""
Storage abstraction layer.
Interface Segregation Principle: StorageBackend abstract class ile kontrat tanımı.
Yeni storage provider eklemek için sadece yeni bir class yazılır.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

import aioboto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings
from app.core.exceptions import FileTooLargeError, InvalidFileTypeError, StorageError
from app.core.i18n import t
from app.core.logging import get_logger

if TYPE_CHECKING:
    from fastapi import UploadFile

logger = get_logger(__name__)


# ── Interface ─────────────────────────────────────────────────────────────────


class StorageBackend(ABC):
    """File storage backend için abstract interface.

    MinIO ve AWS S3 implementasyonları bu interface'i implement eder.
    Upload, delete, URL generation işlemlerini tanımlar.

    Note:
        - Concrete implementation: S3StorageBackend (S3/MinIO için ortak)
        - Storage type Settings.STORAGE_BACKEND ile belirlenir
        - Factory pattern: get_storage() ile instance alınır
    """

    @abstractmethod
    async def upload(self, file: UploadFile, folder: str = "") -> str:
        """Dosyayı storage'a yükler.

        Dosya boyutu ve MIME type validasyonu yapıldıktan sonra benzersiz
        bir key ile storage'a kaydedilir. Key format: {folder}/{uuid}.{ext}

        Args:
            file: Yüklenecek dosya (FastAPI UploadFile)
            folder: Storage içinde hedef klasör (opsiyonel, default: "")

        Returns:
            Yüklenen dosyanın unique key/path'i (örn: "avatars/abc123.jpg")

        Raises:
            FileTooLargeError: Dosya boyutu MAX_UPLOAD_SIZE_BYTES'ı aşarsa
            InvalidFileTypeError: MIME type ALLOWED_UPLOAD_TYPES'da değilse
            StorageError: Upload işlemi başarısız olursa
        """
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Storage'dan dosyayı siler.

        Verilen key'e sahip dosyayı storage'dan kalıcı olarak kaldırır.

        Args:
            key: Silinecek dosyanın storage key'i (upload'dan dönen değer)

        Raises:
            StorageError: Silme işlemi başarısız olursa

        Note:
            Var olmayan bir key için hata fırlatmaz (idempotent)
        """
        ...

    @abstractmethod
    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        """Dosya için presigned URL üretir.

        Geçici olarak dosyaya erişim sağlayan imzalı URL oluşturur.
        URL belirtilen süre sonunda expire olur.

        Args:
            key: Dosyanın storage key'i
            expires_in: URL'nin geçerlilik süresi (saniye, default: 3600)

        Returns:
            Presigned URL string'i (GET request için geçerli)

        Raises:
            StorageError: URL üretimi başarısız olursa

        Example:
            >>> url = await storage.get_url("avatars/abc123.jpg", expires_in=7200)
            >>> # URL 2 saat boyunca geçerli olacak
        """
        ...


# ── Validators ────────────────────────────────────────────────────────────────


async def validate_upload(file: UploadFile) -> bytes:
    """Dosya boyutu ve MIME type doğrular, bytes döndürür.

    Upload öncesi güvenlik kontrolü: max boyut ve whitelist MIME type check.

    Args:
        file: Validate edilecek dosya

    Returns:
        Dosya içeriği (bytes)

    Raises:
        FileTooLargeError: MAX_UPLOAD_SIZE_BYTES aşılırsa
        InvalidFileTypeError: MIME type whitelist'te yoksa
    """
    content = await file.read()

    if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise FileTooLargeError(
            t("error.storage.file_too_large_mb", size_mb=settings.MAX_UPLOAD_SIZE_MB)
        )

    content_type = file.content_type or ""
    if content_type not in settings.ALLOWED_UPLOAD_TYPES:
        raise InvalidFileTypeError(
            t(
                "error.storage.invalid_file_type_detail",
                content_type=content_type,
                allowed=", ".join(settings.ALLOWED_UPLOAD_TYPES),
            )
        )

    return content


def _generate_key(folder: str, filename: str) -> str:
    """Benzersiz S3 dosya anahtarı üretir.

    UUID ile unique name oluşturur, original extension'ı korur.

    Args:
        folder: Klasör path'i (örn: "avatars")
        filename: Original dosya adı (örn: "photo.jpg")

    Returns:
        S3 key (örn: "avatars/a1b2c3d4.jpg")
    """
    ext = Path(filename).suffix.lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"
    return f"{folder.strip('/')}/{unique_name}" if folder else unique_name


# ── S3 / MinIO Backend ────────────────────────────────────────────────────────


class S3StorageBackend(StorageBackend):
    """AWS S3 ve MinIO için ortak implementasyon.

    StorageBackend interface'ini implement eder. S3-compatible storage
    backend'lerinde (AWS S3, MinIO) dosya upload, delete ve presigned URL
    generation işlemlerini gerçekleştirir.

    Attributes:
        _session: aioboto3 session instance (S3 client için)
        _endpoint: S3 endpoint URL (MinIO için gerekli, AWS S3 için None)
        _bucket: Target bucket name
    """

    def __init__(self) -> None:
        """S3/MinIO client session'ı initialize eder.

        Settings'ten S3 credentials (access key, secret key, region) alır ve
        aioboto3 session oluşturur. MinIO için custom endpoint URL set edilir,
        AWS S3 için default endpoints kullanılır (endpoint=None).

        Raises:
            ValueError: Required settings (S3_ACCESS_KEY, S3_SECRET_KEY, etc.)
                eksikse veya geçersizse

        Note:
            - AWS S3: S3_ENDPOINT_URL boş olmalı (default AWS endpoints kullanılır)
            - MinIO: S3_ENDPOINT_URL="http://minio:9000" (local development)
            - Credentials .env dosyasından yüklenir (app/core/config.py)
        """
        self._session = aioboto3.Session(
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
        )
        self._endpoint = settings.S3_ENDPOINT_URL or None
        self._bucket = settings.S3_BUCKET_NAME

    async def upload(self, file: UploadFile, folder: str = "") -> str:
        """Dosya yükler (validation ile).

        File size ve MIME type validation yapar, S3-compatible storage'a yükler.
        Upload sırasında unique key generate eder ve content type bilgisini korur.

        Args:
            file: Yüklenecek dosya (FastAPI UploadFile)
            folder: Storage folder path (örn: "avatars", "documents").
                Boş string ise root'a yüklenir.

        Returns:
            File key/path (storage'daki unique identifier).
            Format: "{folder}/{uuid}.{ext}" veya "{uuid}.{ext}"

        Raises:
            FileTooLargeError: Dosya MAX_UPLOAD_SIZE_BYTES'dan büyükse
            InvalidFileTypeError: MIME type ALLOWED_UPLOAD_TYPES'da değilse
            StorageError: S3 upload işlemi başarısız olursa

        Example:
            >>> file_key = await backend.upload(
            ...     file=upload_file,
            ...     folder="avatars"
            ... )
            >>> # "avatars/a1b2c3d4e5f6.jpg"
        """
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
        except (BotoCoreError, ClientError, OSError) as exc:
            logger.error("upload_failed", error=str(exc))
            raise StorageError(t("error.storage.upload_failed", reason=str(exc))) from exc

        logger.info("file_uploaded", key=key, size=len(content))
        return key

    async def delete(self, key: str) -> None:
        """Dosyayı storage'dan siler.

        Verilen key'e sahip dosyayı S3-compatible storage'dan kalıcı olarak siler.
        Dosya bulunamasa bile hata fırlatmaz (S3 delete_object idempotent).

        Args:
            key: Silinecek dosyanın key'i (upload metodundan dönen değer)

        Raises:
            StorageError: S3 delete işlemi başarısız olursa

        Example:
            >>> await backend.delete("avatars/a1b2c3d4e5f6.jpg")
        """
        try:
            async with self._session.client("s3", endpoint_url=self._endpoint) as s3:
                await s3.delete_object(Bucket=self._bucket, Key=key)
        except (BotoCoreError, ClientError, OSError) as exc:
            logger.error("delete_failed", key=key, error=str(exc))
            raise StorageError(t("error.storage.delete_failed", reason=str(exc))) from exc

        logger.info("file_deleted", key=key)

    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        """Dosya için presigned URL üretir.

        Verilen key'e sahip dosya için temporary download URL generate eder.
        URL belirtilen süre boyunca geçerlidir (authentication gerektirmez).

        Args:
            key: Dosyanın key'i (upload metodundan dönen değer)
            expires_in: URL'nin geçerlilik süresi (saniye). Default 3600 (1 saat)

        Returns:
            Presigned URL (string). Bu URL ile dosya direkt indirilebilir.

        Raises:
            StorageError: URL generation başarısız olursa (örn: dosya yoksa)

        Example:
            >>> url = await backend.get_url(
            ...     "avatars/a1b2c3d4e5f6.jpg",
            ...     expires_in=7200  # 2 saat
            ... )
            >>> # "https://s3.amazonaws.com/bucket/avatars/a1b2...?X-Amz-Expires=7200&..."
        """
        try:
            async with self._session.client("s3", endpoint_url=self._endpoint) as s3:
                url = await s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self._bucket, "Key": key},
                    ExpiresIn=expires_in,
                )
        except (BotoCoreError, ClientError, OSError) as exc:
            raise StorageError(t("error.storage.url_generation_failed", reason=str(exc))) from exc
        return str(url)


# ── Factory ───────────────────────────────────────────────────────────────────


def get_storage() -> StorageBackend:
    """Storage backend'i config'e göre döndürür.

    Factory pattern: STORAGE_BACKEND setting'e göre ilgili implementasyonu döner.

    Returns:
        StorageBackend implementasyonu (S3StorageBackend)

    Raises:
        ValueError: Bilinmeyen backend type ise

    Example:
        >>> storage = get_storage()  # settings.STORAGE_BACKEND="minio"
        >>> isinstance(storage, S3StorageBackend)
        True
    """
    backend = settings.STORAGE_BACKEND.lower()
    if backend in ("s3", "minio"):
        return S3StorageBackend()
    raise ValueError(t("error.storage.unknown_backend", backend=backend))
