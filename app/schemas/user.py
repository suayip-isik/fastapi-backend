"""User şemaları — request/response modelleri."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.schemas.role import AssignRoleRequest, RoleInfo

__all__ = [
    "UserResponse",
    "DeletedUserResponse",
    "UpdateUserRequest",
    "UserStatsResponse",
    "AssignRoleRequest",
]


class UserResponse(BaseModel):
    """User model için response schema.

    Attributes:
        id: User UUID
        email: Kullanıcı email adresi
        username: Kullanıcı adı (opsiyonel)
        full_name: Kullanıcı tam adı (opsiyonel)
        avatar_url: Profil resmi URL'i (opsiyonel)
        role: Kullanıcının rolü (id, name, is_system)
        is_active: Hesap aktif mi
        is_verified: Email doğrulanmış mı
    """

    id: UUID
    email: str
    username: str | None
    full_name: str | None
    avatar_url: str | None
    account_type: str
    role: RoleInfo
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

    Tüm alanlar opsiyoneldir, sadece gönderilen alanlar güncellenir (PATCH semantics).

    Attributes:
        email: Yeni email adresi (benzersiz olmalı)
        full_name: Yeni tam ad (max 255 karakter)
        username: Yeni kullanıcı adı (max 50 karakter, benzersiz olmalı)
        password: Yeni şifre (min 8 karakter, bcrypt ile hash'lenecek)
    """

    email: EmailStr | None = None
    full_name: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=50)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserStatsResponse(BaseModel):
    """Kullanıcı istatistikleri response şeması.

    Attributes:
        total: Toplam kullanıcı sayısı (silinmişler hariç)
        active: Aktif kullanıcı sayısı (is_active=True)
        inactive: Pasif kullanıcı sayısı (is_active=False)
    """

    total: int = Field(description="Toplam kullanıcı sayısı (silinmişler hariç)")
    active: int = Field(description="Aktif kullanıcı sayısı (is_active=True)")
    inactive: int = Field(description="Pasif kullanıcı sayısı (is_active=False)")
