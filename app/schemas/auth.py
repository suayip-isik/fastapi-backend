"""Auth şemaları — request/response modelleri."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        errors = []
        if not any(c.isupper() for c in v):
            errors.append("büyük harf")
        if not any(c.islower() for c in v):
            errors.append("küçük harf")
        if not any(c.isdigit() for c in v):
            errors.append("rakam")
        if errors:
            raise ValueError(f"Şifre şunları içermeli: {', '.join(errors)}")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class OAuthCallbackRequest(BaseModel):
    code: str
    state: str | None = None


class UserResponse(BaseModel):
    id: UUID
    email: str
    username: str | None
    full_name: str | None
    avatar_url: str | None
    role: str
    is_active: bool
    is_verified: bool

    model_config = {"from_attributes": True}
