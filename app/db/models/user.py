"""User modeli."""

from __future__ import annotations

from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import BaseModel, SoftDeleteMixin

if TYPE_CHECKING:
    from app.db.models.oauth_account import OAuthAccount


class UserRole(str, PyEnum):
    """Kullanıcı rol tanımları.

    Sistemdeki kullanıcı yetkilerini belirler. Rol bazlı erişim kontrolü
    (RBAC) için kullanılır.

    Attributes:
        ADMIN: Sistem yöneticisi (tüm yetkiler)
        USER: Normal kullanıcı (standart yetkiler)
        MODERATOR: Moderatör (içerik yönetimi yetkisi)

    Note:
        - Database'de enum member name saklanır (örn: "ADMIN")
        - require_roles() dependency ile endpoint koruması yapılır
    """

    ADMIN = "admin"
    USER = "user"
    MODERATOR = "moderator"


class User(SoftDeleteMixin, BaseModel):
    """Kullanıcı modeli.

    Sistem kullanıcılarını temsil eder. Authentication, authorization ve
    profil bilgilerini içerir. Soft delete destekler (SoftDeleteMixin).

    Attributes:
        email: Benzersiz email adresi (unique index, max 255 karakter)
        username: Opsiyonel kullanıcı adı (unique index, max 50 karakter, nullable)
        hashed_password: bcrypt ile hash'lenmiş şifre (12 rounds, nullable - OAuth kullanıcılar için)
        full_name: Kullanıcının tam adı (max 255 karakter, nullable)
        avatar_url: Profil resmi URL (nullable)
        role: UserRole enum (ADMIN, USER, MODERATOR, default: USER)
        is_active: Hesap aktif mi (deaktif edilebilir, default: True)
        is_verified: Email doğrulanmış mı (default: False)
        totp_secret: TOTP 2FA secret (Fernet ile şifrelenmiş, nullable)
        totp_enabled: 2FA aktif mi (default: False)
        oauth_accounts: OAuth bağlantıları (relationship, cascade delete)
        created_at: Kayıt tarihi (BaseModel'den inherit, auto)
        updated_at: Son güncelleme (BaseModel'den inherit, auto)
        deleted_at: Soft delete zamanı (SoftDeleteMixin'den inherit, nullable)
        id: UUID primary key (BaseModel'den inherit)

    Example:
        >>> from app.core.security import get_password_hash
        >>> user = User(
        ...     email="test@example.com",
        ...     username="testuser",
        ...     hashed_password=get_password_hash("password123"),
        ...     role=UserRole.USER
        ... )

    Note:
        - hashed_password asla direkt set edilmez, get_password_hash() kullan
        - BaseModel'den UUID id, timestamps (created_at, updated_at) inherit eder
        - SoftDeleteMixin'den deleted_at, is_deleted property inherit eder
        - OAuth kullanıcıları için hashed_password None olabilir
        - OAuth account'lar cascade delete ile otomatik silinir
        - totp_secret Fernet encryption ile şifrelenmiş saklanır
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True, index=True)
    hashed_password: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # OAuth users may not have password
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.USER, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 2FA / TOTP
    totp_secret: Mapped[str | None] = mapped_column(Text, nullable=True)  # Fernet şifreli
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    oauth_accounts: Mapped[list[OAuthAccount]] = relationship(
        "OAuthAccount", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """Debug/log amacli kisa kullanici gosterimini dondurur."""
        return f"<User {self.email}>"
