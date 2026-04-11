"""Ortak Pydantic şemaları — tüm modüllerde paylaşılır."""

from __future__ import annotations

import base64
import binascii
import json
from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel

T = TypeVar("T")


def calculate_pages(total: int, size: int) -> int:
    """Toplam kayıt sayısı ve sayfa boyutundan toplam sayfa sayısını hesaplar.

    Tamsayı bölme ile yukarı yuvarlama (ceiling division) uygular.
    Toplam kayıt yoksa 0 döner.

    Args:
        total: Toplam kayıt sayısı (filtresiz). Negatif değer verilmemeli.
        size: Sayfa başına kayıt sayısı. Sıfır verilmemeli (ZeroDivisionError).

    Returns:
        Toplam sayfa sayısı. total=0 ise 0, aksi hâlde ceil(total / size).

    Example:
        >>> calculate_pages(total=95, size=10)
        10
        >>> calculate_pages(total=100, size=10)
        10
        >>> calculate_pages(total=0, size=10)
        0
    """
    return (total + size - 1) // size if total > 0 else 0


def encode_cursor(created_at: datetime, id: UUID) -> str:
    """(created_at, id) çiftini opak base64 cursor string'ine kodlar.

    Cursor tabanlı sayfalama için kullanılır. created_at ve id değerleri
    JSON payload'una dönüştürülüp base64 ile encode edilir. Üretilen cursor
    istemci tarafına güvenle iletilebilir; decode edilmesi için decode_cursor
    kullanılır.

    Args:
        created_at: Kaydın oluşturulma zamanı (UTC datetime). ISO format ile
            serileştirilir.
        id: Kaydın benzersiz UUID'si. Sıralama bağlantısını (tie-breaking)
            sağlar.

    Returns:
        Base64 URL-safe olmayan (standart) encoded opak cursor string'i.

    Note:
        Üretilen cursor değeri istemci tarafından yorumlanmamalı; yalnızca
        bir sonraki sayfa isteğinde cursor parametresi olarak iletilmelidir.

    Example:
        >>> from datetime import datetime, UTC
        >>> from uuid import uuid4
        >>> cursor = encode_cursor(datetime.now(UTC), uuid4())
        >>> isinstance(cursor, str)
        True
    """
    payload = {"ts": created_at.isoformat(), "id": str(id)}
    return base64.b64encode(json.dumps(payload).encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    """encode_cursor ile üretilen cursor string'ini çözerek orijinal değerlere dönüştürür.

    Base64 decode → JSON parse → (datetime, UUID) dönüşümü gerçekleştirir.
    Herhangi bir aşamada hata oluşursa AppValidationError fırlatır.

    Args:
        cursor: encode_cursor tarafından üretilmiş base64 cursor string'i.

    Returns:
        (created_at, id) çifti: sırasıyla datetime ve UUID nesneleri.

    Raises:
        AppValidationError: Cursor değeri geçersiz base64, bozuk JSON,
            eksik alan veya hatalı datetime/UUID formatı içeriyorsa.

    Note:
        İstemciden gelen tüm cursor değerleri bu fonksiyon üzerinden geçirilmeli;
        ham base64 decode doğrudan kullanılmamalıdır.

    Example:
        >>> from datetime import datetime, UTC
        >>> from uuid import uuid4
        >>> dt, uid = datetime.now(UTC), uuid4()
        >>> cursor = encode_cursor(dt, uid)
        >>> decoded_dt, decoded_uid = decode_cursor(cursor)
        >>> decoded_uid == uid
        True
    """
    try:
        payload = json.loads(base64.b64decode(cursor).decode())
        return datetime.fromisoformat(payload["ts"]), UUID(payload["id"])
    except (binascii.Error, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        from app.core.exceptions import ValidationError as AppValidationError

        raise AppValidationError("Geçersiz cursor değeri.") from exc


class PaginatedResponse(BaseModel, Generic[T]):
    """Offset tabanlı sayfalama için generic response schema.

    List endpoint'leri için kullanılır. Items + metadata döner.
    Küçük-orta boyutlu veri setleri için uygundur. Büyük veri setlerinde
    cursor-based pagination (CursorPaginatedResponse) tercih edilmelidir.

    Attributes:
        items: Liste elemanları (generic type T)
        total: Toplam kayıt sayısı (filtresiz)
        page: Mevcut sayfa numarası (1-indexed)
        size: Sayfa başına kayıt sayısı
        pages: Toplam sayfa sayısı

    Example:
        >>> response = PaginatedResponse[UserResponse](
        ...     items=[user1, user2],
        ...     total=100,
        ...     page=1,
        ...     size=10,
        ...     pages=10
        ... )
    """

    items: list[T]
    total: int
    page: int
    size: int
    pages: int


class MessageResponse(BaseModel):
    """Basit mesaj response schema.

    Başarılı işlemler veya bilgilendirme mesajları için kullanılır.
    Genellikle create, update, delete işlemlerinden döner.

    Attributes:
        message: Kullanıcıya gösterilecek mesaj metni

    Example:
        >>> response = MessageResponse(message="Kullanıcı başarıyla oluşturuldu")
    """

    message: str


class ErrorDetail(BaseModel):
    """Hata detay schema.

    Standart hata response'larının içindeki detay objesi. Global exception
    handler tarafından oluşturulur. Request ID debugging için kullanılır.

    Attributes:
        code: Hata kodu (örn: "VALIDATION_ERROR", "NOT_FOUND")
        message: Kullanıcıya gösterilecek hata mesajı
        request_id: Request izleme ID'si (debugging için)
        details: Ek hata detayları (örn: validation errors, field errors)

    Example:
        >>> error = ErrorDetail(
        ...     code="VALIDATION_ERROR",
        ...     message="Email formatı geçersiz",
        ...     request_id="req-123",
        ...     details={"field": "email", "error": "invalid format"}
        ... )
    """

    code: str
    message: str
    request_id: str | None = None
    details: dict[str, object] | list[object] | None = None


class ErrorResponse(BaseModel):
    """Standart hata response schema.

    Tüm API hataları bu formatta döner. Global exception handler
    tarafından otomatik oluşturulur. RFC 7807 Problem Details benzeri.

    Attributes:
        error: ErrorDetail objesi (kod, mesaj, detaylar)

    Example:
        >>> response = ErrorResponse(
        ...     error=ErrorDetail(
        ...         code="NOT_FOUND",
        ...         message="Kullanıcı bulunamadı",
        ...         request_id="req-456"
        ...     )
        ... )
    """

    error: ErrorDetail


class CursorPaginatedResponse(BaseModel, Generic[T]):
    """Cursor tabanlı sayfalama için generic response schema.

    Büyük veri setleri için offset-based pagination'dan daha performanslı.
    Cursor (created_at, id) çiftinden base64 encode edilerek oluşturulur.
    Sonraki sayfa için next_cursor kullanılır.

    Attributes:
        items: Liste elemanları (generic type T)
        next_cursor: Sonraki sayfa cursor'ı (None = son sayfa)
        has_more: Daha fazla kayıt var mı
        size: Bu sayfadaki kayıt sayısı

    Example:
        >>> response = CursorPaginatedResponse[UserResponse](
        ...     items=[user1, user2, user3],
        ...     next_cursor="eyJpZCI6IjEyMy...",
        ...     has_more=True,
        ...     size=3
        ... )
        >>> # Sonraki sayfa için: GET /users?cursor=eyJpZCI6IjEyMy...
    """

    items: list[T]
    next_cursor: str | None  # None = son sayfa
    has_more: bool
    size: int
