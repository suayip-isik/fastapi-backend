"""TOTPBackupCode modeli — DB'de saklanan backup kodlar (bcrypt hash)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import BaseModel


class TOTPBackupCode(BaseModel):
    """Kullanıcının tek kullanımlık TOTP yedek kodunu temsil eden veritabanı modeli.

    2FA etkinleştirilmiş kullanıcıların TOTP cihazına erişim kaybetmeleri
    durumunda giriş yapabilmeleri için üretilen yedek kodları saklar. Her kod
    bcrypt ile hash'lenerek depolanır ve yalnızca bir kez kullanılabilir.

    Attributes:
        user_id: Kodun ait olduğu kullanıcının UUID'si (CASCADE ile silinir).
        code_hash: Bcrypt ile hash'lenmiş yedek kod değeri.
        is_used: Kodun daha önce kullanılıp kullanılmadığı.
        used_at: Kodun kullanıldığı UTC zaman damgası (kullanılmamışsa None).

    Note:
        - (user_id, is_used) çifti üzerinde bileşik indeks bulunur (hızlı aktif kod sorguları için).
        - Yeni backup kod seti üretildiğinde eski tüm kodlar silinir.
    """

    __tablename__ = "totp_backup_codes"
    __table_args__ = (Index("ix_totp_backup_user_used", "user_id", "is_used"),)

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
