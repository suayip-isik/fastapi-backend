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
    ADMIN = "admin"
    USER = "user"
    MODERATOR = "moderator"


class User(SoftDeleteMixin, BaseModel):
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
        return f"<User {self.email}>"
