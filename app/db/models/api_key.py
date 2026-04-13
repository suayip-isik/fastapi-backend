"""API Key modeli — servis-servis veya makine istemcileri için."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import BaseModel

if TYPE_CHECKING:
    from app.db.models.user import User


class APIKey(BaseModel):
    """API Key modeli.

    Programmatic API erişimi için kullanıcıların API key'lerini saklar.
    Key'ler bcrypt ile hash'lenerek saklanır. X-API-Key header ile
    authentication yapılabilir. Scope'lar kullanıcının yetkilerini
    daraltmak için uygulanır.

    Attributes:
        user_id: Key sahibi User ID (foreign key, CASCADE delete)
        name: Key'e verilen isim/tanımlayıcı (max 100 karakter)
        key_prefix: Key'in ilk 8 karakteri (gösterim/tanımlama için)
        key_hash: bcrypt ile hash'lenmiş key değeri
        scopes: Boşlukla ayrılmış permission scope listesi
        last_used_at: Son kullanım zamanı (nullable, otomatik güncellenir)
        expires_at: Key expiration zamanı (nullable)
        is_active: Key'in aktif olup olmadığı (soft delete için)
        user: User modeline relationship

    Note:
        - Plain key sadece oluşturma anında döner, sonra erişilemez
        - key_hash bcrypt ile saklanır (JWT signing gibi değil)
        - last_used_at her kullanımda güncellenir
        - Expired veya is_active=False key'ler otomatik reddedilir
        - key_prefix güvenlik açısından güvenli (hash collision riski yok)

    Example:
        >>> api_key = APIKey(
        ...     user_id=user.id,
        ...     name="Production API Key",
        ...     key_prefix="sk_prod_",
        ...     key_hash=get_password_hash(generated_key),
        ...     scopes="read write",
        ...     is_active=True
        ... )
    """

    __tablename__ = "api_keys"
    __table_args__ = (
        Index("ix_api_keys_user_active", "user_id", "is_active"),
        Index("ix_api_keys_expires_at", "expires_at"),
        UniqueConstraint("user_id", "key_prefix", name="uq_api_key_user_prefix"),
    )

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
        """String representation.

        Returns:
            Key prefix ve ismiyle birlikte API key gösterimi.

        Example:
            <APIKey sk_prod_... (Production API Key)>
        """
        return f"<APIKey {self.key_prefix}... ({self.name})>"
