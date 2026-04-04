"""User şemaları — request/response modelleri."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.db.models.user import UserRole


class UserResponse(BaseModel):
    """User model için response schema.

    User bilgilerini client'a dönerken kullanılır. Hassas bilgiler
    (password_hash, totp_secret) exclude edilir. SQLAlchemy model'den
    otomatik dönüşüm için from_attributes=True ayarlanmıştır.

    Attributes:
        id: User UUID (primary key)
        email: Kullanıcı email adresi
        username: Kullanıcı adı (opsiyonel)
        full_name: Kullanıcı tam adı (opsiyonel)
        avatar_url: Profil resmi URL'i (opsiyonel)
        role: Kullanıcı rolü (ADMIN, USER, MODERATOR)
        is_active: Hesap aktif mi (soft delete için)
        is_verified: Email doğrulanmış mı

    Example:
        >>> user = UserResponse(
        ...     id=UUID("..."),
        ...     email="user@example.com",
        ...     username="johndoe",
        ...     full_name="John Doe",
        ...     avatar_url=None,
        ...     role="USER",
        ...     is_active=True,
        ...     is_verified=True
        ... )
    """

    id: UUID
    email: str
    username: str | None
    full_name: str | None
    avatar_url: str | None
    role: UserRole
    is_active: bool
    is_verified: bool

    model_config = {"from_attributes": True}


class DeletedUserResponse(UserResponse):
    """Soft-delete ile silinmiş kullanıcılar için response schema.

    UserResponse'u genişletir; silinme zamanını da içerir.
    Yalnızca `GET /users/deleted` (admin trash view) endpoint'inde kullanılır.

    Attributes:
        deleted_at: Kullanıcının silindiği zaman damgası.
    """

    deleted_at: datetime


class UpdateUserRequest(BaseModel):
    """Kullanıcı bilgilerini güncelleme için request schema.

    Kullanıcının kendi profilini veya admin'in başka kullanıcıyı güncellemesi için.
    Tüm alanlar opsiyoneldir, sadece gönderilen alanlar güncellenir (PATCH semantics).

    Attributes:
        email: Yeni email adresi (EmailStr validation, benzersiz olmalı)
        full_name: Yeni tam ad (max 255 karakter)
        username: Yeni kullanıcı adı (max 50 karakter, benzersiz olmalı)
        password: Yeni şifre (min 8 karakter, bcrypt ile hash'lenecek)

    Example:
        >>> # Sadece email güncelleme
        >>> request = UpdateUserRequest(email="newemail@example.com")
        >>> # Birden fazla alan güncelleme
        >>> request = UpdateUserRequest(
        ...     email="newemail@example.com",
        ...     full_name="Jane Doe",
        ...     username="janedoe"
        ... )
    """

    email: EmailStr | None = None
    full_name: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=50)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserStatsResponse(BaseModel):
    """Kullanıcı istatistikleri response şeması.

    Sistemdeki aktif, pasif ve toplam kullanıcı sayılarını döndürür.
    Soft-delete ile silinmiş kullanıcılar sayımlara dahil edilmez.

    Attributes:
        total: Toplam kullanıcı sayısı (silinmişler hariç)
        active: Aktif kullanıcı sayısı (is_active=True)
        inactive: Pasif kullanıcı sayısı (is_active=False)
    """

    total: int = Field(description="Toplam kullanıcı sayısı (silinmişler hariç)")
    active: int = Field(description="Aktif kullanıcı sayısı (is_active=True)")
    inactive: int = Field(description="Pasif kullanıcı sayısı (is_active=False)")


class ChangeRoleRequest(BaseModel):
    """Kullanıcı rolü değiştirme için request schema.

    Sadece ADMIN yetkisi olan kullanıcılar başka kullanıcıların rolünü
    değiştirebilir. Role enum validation ile kontrol edilir.

    Attributes:
        role: Yeni kullanıcı rolü (UserRole enum: ADMIN, USER, MODERATOR)

    Example:
        >>> request = ChangeRoleRequest(role=UserRole.MODERATOR)
    """

    role: UserRole
