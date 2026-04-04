"""Bildirim modeli — in-app notification."""

from __future__ import annotations

from enum import Enum as PyEnum
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import BaseModel


class NotificationType(str, PyEnum):
    """Bildirim tipleri enum'u.

    Kullanıcılara gönderilen notification'ların türlerini tanımlar.
    Her tip farklı UI renk ve ikon ile gösterilebilir.

    Attributes:
        INFO: Bilgilendirme notification'ı (mavi)
        SUCCESS: Başarılı işlem bildirimi (yeşil)
        WARNING: Uyarı bildirimi (turuncu)
        ERROR: Hata bildirimi (kırmızı)
        SYSTEM: Sistem bildirimi (gri)
        MENTION: Mention/etiketleme bildirimi
        FILE_PROCESSED: Dosya işleme tamamlandı bildirimi
    """

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    # Uygulama spesifik
    SYSTEM = "system"
    MENTION = "mention"
    FILE_PROCESSED = "file_processed"


class Notification(BaseModel):
    """Bildirim modeli.

    Kullanıcılara gönderilen in-app notification'ları saklar.
    WebSocket ile real-time push veya polling ile alınabilir.
    Cascade delete ile kullanıcı silindiğinde bildirimleri de silinir.

    Attributes:
        user_id: Bildirim alıcısı User ID (foreign key, CASCADE delete)
        type: Bildirim tipi (NotificationType enum, varsayılan INFO)
        title: Bildirim başlığı (max 255 karakter)
        body: Bildirim detayı/içeriği (nullable, Text)
        data: Ek JSON data (nullable, JSONB) - webhook payload, URL vb.
        is_read: Okundu mu (varsayılan False, indexed)

    Note:
        - is_read varsayılan False, okunmamış notification'lar için index
        - user_id indexed, kullanıcıya ait bildirimleri hızlı sorgular
        - WebSocket broadcast ile real-time gönderilir
        - Eski notification'lar ARQ cron job ile temizlenebilir
        - data field'ı her notification tipine özgü ek bilgi için kullanılır

    Example:
        >>> notif = Notification(
        ...     user_id=user.id,
        ...     title="Yeni Mesaj",
        ...     body="Profilinize yorum yapıldı",
        ...     type=NotificationType.MENTION,
        ...     data={"comment_id": "123", "author": "johndoe"}
        ... )
    """

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_read", "user_id", "is_read"),
        Index("ix_notifications_user_created", "user_id", "created_at"),
    )

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
        """Notification objesinin string temsili.

        Returns:
            str: Notification tipi ve alıcı user_id içeren string
        """
        return f"<Notification {self.type} → {self.user_id}>"
