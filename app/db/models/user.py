"""User modeli."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import BaseModel, SoftDeleteMixin

if TYPE_CHECKING:
    from app.db.models.role import Role


class User(SoftDeleteMixin, BaseModel):
    """Kullanıcı modeli.

    Sistem kullanıcılarını temsil eder. Authentication, authorization ve
    profil bilgilerini içerir. Soft delete destekler (SoftDeleteMixin).
    Rol ataması `role_id` FK üzerinden `Role` modeline yapılır.

    Attributes:
        email: Benzersiz email adresi (unique index, max 255 karakter)
        username: Opsiyonel kullanıcı adı (unique index, max 50 karakter, nullable)
        hashed_password: bcrypt ile hash'lenmiş şifre (12 rounds, nullable)
        full_name: Kullanıcının tam adı (max 255 karakter, nullable)
        avatar_url: Profil resmi URL (nullable)
        role_id: Atanmış rolün UUID'si (FK → roles.id)
        role: Role ilişkisi (selectin ile otomatik yüklenir)
        is_active: Hesap aktif mi (deaktif edilebilir, default: True)
        is_verified: Email doğrulanmış mı (default: False)
        totp_secret: TOTP 2FA secret (Fernet ile şifrelenmiş, nullable)
        totp_enabled: 2FA aktif mi (default: False)
        created_at: Kayıt tarihi (BaseModel'den inherit, auto)
        updated_at: Son güncelleme (BaseModel'den inherit, auto)
        deleted_at: Soft delete zamanı (SoftDeleteMixin'den inherit, nullable)
        id: UUID primary key (BaseModel'den inherit)

    Note:
        - hashed_password asla direkt set edilmez, hash_password() kullan
        - role ilişkisi lazy="selectin" ile otomatik yüklenir
        - totp_secret Fernet encryption ile şifrelenmiş saklanır
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True, index=True)
    hashed_password: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    role_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("roles.id"),
        nullable=False,
        index=True,
    )
    role: Mapped[Role] = relationship("Role", lazy="selectin")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 2FA / TOTP
    totp_secret: Mapped[str | None] = mapped_column(Text, nullable=True)  # Fernet şifreli
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:
        """Debug/log amacli kisa kullanici gosterimini dondurur."""
        return f"<User {self.email}>"
