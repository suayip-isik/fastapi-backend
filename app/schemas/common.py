"""Ortak Pydantic şemaları — tüm modüllerde paylaşılır."""

from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel

T = TypeVar("T")


def encode_cursor(created_at: datetime, id: UUID) -> str:
    """(created_at, id) çiftini opak base64 cursor'a çevirir."""
    payload = {"ts": created_at.isoformat(), "id": str(id)}
    return base64.b64encode(json.dumps(payload).encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    """encode_cursor ile üretilen cursor'ı çözer."""
    payload = json.loads(base64.b64decode(cursor).decode())
    return datetime.fromisoformat(payload["ts"]), UUID(payload["id"])


class PaginatedResponse(BaseModel, Generic[T]):
    """Sayfalı liste response şeması."""

    items: list[T]
    total: int
    page: int
    size: int
    pages: int


class MessageResponse(BaseModel):
    """Basit mesaj response şeması."""

    message: str


class ErrorDetail(BaseModel):
    """Hata detay şeması."""

    code: str
    message: str
    request_id: str | None = None
    details: dict[str, object] | list[object] | None = None


class ErrorResponse(BaseModel):
    """Standart hata response şeması."""

    error: ErrorDetail


class CursorPaginatedResponse(BaseModel, Generic[T]):
    """Cursor tabanlı sayfalama — büyük veri setleri için."""

    items: list[T]
    next_cursor: str | None  # None = son sayfa
    has_more: bool
    size: int
