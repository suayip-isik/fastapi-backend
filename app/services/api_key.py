"""
APIKeyService — API key oluşturma, listeleme, silme ve doğrulama.

Key formatı: sk_live_<random_hex_40>
İlk 12 karakter prefix olarak saklanır, geri kalanı bcrypt ile hashlenir.
Key sadece oluşturulurken döndürülür — sonra gösterilmez.
"""

from __future__ import annotations

import contextlib
import secrets
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.core.exceptions import AuthenticationError, NotFoundError
from app.core.security import hash_password, verify_password
from app.db.repositories.api_key import APIKeyRepository

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models.api_key import APIKey

_KEY_PREFIX = "sk_live_"
_KEY_BYTES = 40  # raw random bytes → hex = 80 chars


def _generate_raw_key() -> str:
    return f"{_KEY_PREFIX}{secrets.token_hex(_KEY_BYTES)}"


def _split_key(raw_key: str) -> tuple[str, str]:
    """prefix (ilk 12 char) + secret (geri kalanı) olarak böl."""
    return raw_key[:12], raw_key[12:]


class APIKeyService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = APIKeyRepository(session)

    async def create(
        self,
        user_id: UUID,
        name: str,
        scopes: list[str] | None = None,
        expires_at: datetime | None = None,
    ) -> tuple[str, APIKey]:
        """
        Yeni API key oluşturur.
        Returns: (raw_key, APIKey) — raw_key sadece bir kez döner.
        """
        raw_key = _generate_raw_key()
        prefix, secret_part = _split_key(raw_key)

        api_key = await self._repo.create(
            user_id=user_id,
            name=name,
            key_prefix=prefix,
            key_hash=hash_password(secret_part),
            scopes=" ".join(scopes or []),
            expires_at=expires_at,
            is_active=True,
        )
        return raw_key, api_key

    async def list_for_user(self, user_id: UUID) -> list[APIKey]:
        return await self._repo.get_active_by_user(user_id)

    async def revoke(self, key_id: UUID, user_id: UUID) -> None:
        """Kullanıcının kendi key'ini iptal eder."""
        api_key = await self._repo.get_by_id(key_id)
        if not api_key or api_key.user_id != user_id:
            raise NotFoundError("API key bulunamadı.")
        await self._repo.update(key_id, is_active=False)

    async def authenticate(self, raw_key: str) -> APIKey:
        """
        Ham key'i doğrular ve APIKey nesnesini döndürür.
        Geçersizse AuthenticationError fırlatır.
        """
        if not raw_key.startswith(_KEY_PREFIX):
            raise AuthenticationError("Geçersiz API key formatı.")

        prefix, secret_part = _split_key(raw_key)
        candidates = await self._repo.get_active_by_prefix(prefix)

        for api_key in candidates:
            if not verify_password(secret_part, api_key.key_hash):
                continue

            # Süre kontrolü
            if api_key.expires_at and api_key.expires_at < datetime.now(UTC):
                raise AuthenticationError("API key süresi dolmuş.")

            # last_used_at güncelle (non-blocking — hata fırlatmaz)
            with contextlib.suppress(Exception):
                await self._repo.update(api_key.id, last_used_at=datetime.now(UTC))

            return api_key

        raise AuthenticationError("Geçersiz API key.")
