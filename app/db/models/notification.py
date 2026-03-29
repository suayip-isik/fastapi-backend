"""Bildirim modeli — in-app notification."""

from __future__ import annotations

from enum import Enum as PyEnum
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import BaseModel


class NotificationType(str, PyEnum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    # Uygulama spesifik
    SYSTEM = "system"
    MENTION = "mention"
    FILE_PROCESSED = "file_processed"


class Notification(BaseModel):
    __tablename__ = "notifications"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType),
        nullable=False,
        default=NotificationType.INFO,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)  # Extra payload
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<Notification {self.type} → {self.user_id}>"
