"""User şemaları."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UpdateUserRequest(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=50)
    password: str | None = Field(default=None, min_length=8)


class UserListResponse(BaseModel):
    id: UUID
    email: str
    username: str | None
    full_name: str | None
    avatar_url: str | None
    role: str
    is_active: bool
    is_verified: bool

    model_config = {"from_attributes": True}
