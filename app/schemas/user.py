"""User şemaları — request/response modelleri."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.i18n import t
from app.schemas.role import AssignRoleRequest, RoleInfo

__all__ = [
    "UserResponse",
    "DeletedUserResponse",
    "CreateAdminUserRequest",
    "UpdateOwnProfileRequest",
    "UpdateOwnEmailRequest",
    "UpdateOwnPasswordRequest",
    "AdminUpdateUserProfileRequest",
    "AdminChangeUserEmailRequest",
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
    surface: str
    role: RoleInfo
    is_active: bool
    is_verified: bool
    has_pending_email: bool
    verification_required: bool

    model_config = {"from_attributes": True}


class DeletedUserResponse(UserResponse):
    """Soft-delete ile silinmiş kullanıcılar için response schema.

    UserResponse'u genişletir; silinme zamanını da içerir.
    Yalnızca `GET /users/deleted` (admin trash view) endpoint'inde kullanılır.

    Attributes:
        deleted_at: Kullanıcının silindiği zaman damgası.
    """

    deleted_at: datetime


class UpdateOwnProfileRequest(BaseModel):
    """Kullanıcının kendi temel profil alanlarını güncelleme isteği."""

    full_name: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=50)


class UpdateOwnEmailRequest(BaseModel):
    """Kullanıcının kendi e-posta değişikliği isteği."""

    email: EmailStr = Field(..., max_length=255)
    current_password: str = Field(..., min_length=8, max_length=128)


class UpdateOwnPasswordRequest(BaseModel):
    """Kullanıcının kendi şifre değişikliği isteği."""

    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password", mode="after")
    @classmethod
    def _validate_password_strength(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not any(c.isupper() for c in v):
            raise ValueError(t("validation.password.missing_upper"))
        if not any(c.isdigit() for c in v):
            raise ValueError(t("validation.password.missing_digit"))
        return v


class AdminUpdateUserProfileRequest(BaseModel):
    """Admin user-management için kullanıcı güncelleme isteği."""

    full_name: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=50)


class AdminChangeUserEmailRequest(BaseModel):
    """Admin user-management ile hedef kullanıcının e-posta değişikliği isteği."""

    email: EmailStr = Field(..., max_length=255)


class CreateAdminUserRequest(BaseModel):
    """Admin panelinden yeni admin kullanıcı oluşturma isteği."""

    email: EmailStr = Field(..., max_length=255)
    role_name: str = Field(..., min_length=1, max_length=50)
    full_name: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=50)


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
