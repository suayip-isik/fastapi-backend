"""API Key modeli — servis-servis veya makine istemcileri için."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import BaseModel

if TYPE_CHECKING:
    from app.db.models.user import User


class APIKey(BaseModel):
    __tablename__ = "api_keys"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_prefix: Mapped[str] = mapped_column(
        String(12), nullable=False
    )  # İlk 8 char (gösterim için)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False)  # bcrypt hash
    scopes: Mapped[str] = mapped_column(Text, nullable=False, default="")  # Boşlukla ayrılmış
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationship
    user: Mapped[User] = relationship("User", lazy="select")

    def __repr__(self) -> str:
        return f"<APIKey {self.key_prefix}... ({self.name})>"
