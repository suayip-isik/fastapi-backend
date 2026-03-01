"""Ortak Pydantic şemaları — tüm modüllerde paylaşılır."""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


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
    details: dict | None = None


class ErrorResponse(BaseModel):
    """Standart hata response şeması."""
    error: ErrorDetail
