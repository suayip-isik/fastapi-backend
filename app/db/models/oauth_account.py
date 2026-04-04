"""OAuth hesap modeli — social login provider bilgilerini saklar."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import BaseModel

if TYPE_CHECKING:
    from app.db.models.user import User


class OAuthAccount(BaseModel):
    """OAuth hesap bağlantısı modeli.

    Kullanıcıların OAuth provider'larla (Google, GitHub) bağlantılarını
    saklar. Bir kullanıcı birden fazla provider'a bağlanabilir.

    Attributes:
        user_id: Bağlı User ID (foreign key). Cascade delete ile user silinirse
            OAuth account da silinir.
        provider: OAuth provider adı (google, github). Maksimum 50 karakter.
        provider_user_id: Provider'daki unique user ID. Maksimum 255 karakter.
        access_token: OAuth access token (nullable). Text olarak saklanır.
        refresh_token: OAuth refresh token (nullable). Text olarak saklanır.
        email: Provider'dan alınan email adresi (nullable). Maksimum 255 karakter.
        user: User relationship (back_populates='oauth_accounts').

    Note:
        - user_id indexed (hızlı query için)
        - User silinirse OAuth account cascade delete
        - Provider ve provider_user_id kombinasyonu unique olmalı (DB constraint)
        - Token'lar hassas veri olduğu için dikkatli kullanılmalı

    Example:
        >>> oauth_acc = OAuthAccount(
        ...     user_id=user.id,
        ...     provider="google",
        ...     provider_user_id="1234567890",
        ...     email="user@gmail.com"
        ... )
    """

    __tablename__ = "oauth_accounts"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_user"),
        Index("ix_oauth_user_provider", "user_id", "provider"),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # google, github
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="oauth_accounts")

    def __repr__(self) -> str:
        """OAuthAccount nesnesinin string temsilini döndürür.

        Returns:
            Provider ve provider_user_id bilgilerini içeren string.

        Example:
            >>> str(oauth_acc)
            '<OAuthAccount google:1234567890>'
        """
        return f"<OAuthAccount {self.provider}:{self.provider_user_id}>"
