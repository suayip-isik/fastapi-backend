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

from app.core.config import settings
from app.core.exceptions import AuthenticationError, NotFoundError
from app.core.logging import get_logger
from app.core.security import hash_password, verify_password
from app.db.models.audit_log import AuditAction
from app.db.repositories.api_key import APIKeyRepository
from app.services.base import AuditableMixin

_logger = get_logger(__name__)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models.api_key import APIKey
    from app.services.audit import AuditService


def _generate_raw_key() -> str:
    """Yeni bir ham API key degeri uretir."""
    return f"{settings.API_KEY_PREFIX}{secrets.token_hex(settings.API_KEY_BYTES)}"


def _split_key(raw_key: str) -> tuple[str, str]:
    """prefix (ilk 12 char) + secret (geri kalanı) olarak böl."""
    return raw_key[:12], raw_key[12:]


class APIKeyService(AuditableMixin):
    """API key yönetimi için servis sınıfı.

    Bu servis, API key oluşturma, listeleme, iptal etme ve doğrulama
    işlemlerini yönetir. Key'ler güvenlik için prefix ve hash olarak
    ayrı saklanır.

    Attributes:
        _repo: API key veritabanı işlemleri için repository.
        _audit: Audit log servisi (opsiyonel).
    """

    def __init__(self, session: AsyncSession, audit: AuditService | None = None) -> None:
        self._repo = APIKeyRepository(session)
        self._audit = audit

    async def create(
        self,
        user_id: UUID,
        name: str,
        scopes: list[str] | None = None,
        expires_at: datetime | None = None,
    ) -> tuple[str, APIKey]:
        """Yeni bir API key oluşturur.

        Güvenli bir rastgele key üretir, prefix ve hash olarak saklar.
        Ham key sadece bu metot tarafından bir kez döndürülür ve sonra
        erişilemez.

        Args:
            user_id: Key'in ait olacağı kullanıcının UUID'si.
            name: API key için kullanıcı dostu bir isim.
            scopes: Key'in erişim izinleri listesi. Varsayılan boş liste.
            expires_at: Key'in geçerlilik bitiş tarihi. None ise süresiz.

        Returns:
            tuple[str, APIKey]: Ham key string'i ve oluşturulan APIKey nesnesi.
                Ham key formatı: ``sk_live_<80_hex_karakter>``

        Example:
            >>> raw_key, api_key = await service.create(
            ...     user_id=user.id,
            ...     name="Production API",
            ...     scopes=["read", "write"]
            ... )
            >>> print(raw_key)  # sk_live_abc123...
        """
        raw_key = _generate_raw_key()
        prefix, secret_part = _split_key(raw_key)
        normalized_scopes = sorted(set(scopes or []))

        api_key = await self._repo.create(
            user_id=user_id,
            name=name,
            key_prefix=prefix,
            key_hash=hash_password(secret_part),
            scopes=" ".join(normalized_scopes),
            expires_at=expires_at,
            is_active=True,
        )
        await self._audit_log(
            AuditAction.API_KEY_CREATED,
            user_id=user_id,
            extra={"key_name": name, "key_prefix": prefix},
        )
        return raw_key, api_key

    async def list_for_user(self, user_id: UUID) -> list[APIKey]:
        """Kullanıcının aktif API key'lerini listeler.

        Sadece aktif (iptal edilmemiş) key'leri döndürür. Süresi dolmuş
        key'ler de listeye dahil edilir.

        Args:
            user_id: Key'leri listelenecek kullanıcının UUID'si.

        Returns:
            list[APIKey]: Kullanıcının aktif API key'lerinin listesi.
                Liste boş olabilir.
        """
        return await self._repo.get_active_by_user(user_id)

    async def revoke(self, key_id: UUID, user_id: UUID) -> None:
        """Kullanıcının API key'ini iptal eder.

        Key'i soft-delete yapar (is_active=False). İptal edilen key
        artık authenticate işlemlerinde kullanılamaz.

        Args:
            key_id: İptal edilecek API key'in UUID'si.
            user_id: İşlemi yapan kullanıcının UUID'si. Key bu kullanıcıya
                ait olmalıdır.

        Raises:
            NotFoundError: Key bulunamadı veya kullanıcıya ait değil.
        """
        api_key = await self._repo.get_by_id(key_id)
        if not api_key or api_key.user_id != user_id:
            raise NotFoundError("API key bulunamadı.")
        await self._repo.update(key_id, is_active=False)
        await self._audit_log(
            AuditAction.API_KEY_REVOKED,
            user_id=user_id,
            extra={"key_name": api_key.name, "key_prefix": api_key.key_prefix},
        )

    async def revoke_all_for_user(self, user_id: UUID, *, reason: str) -> None:
        """Kullanıcının tüm aktif API key'lerini iptal eder."""
        api_keys = await self._repo.get_active_by_user(user_id)
        for api_key in api_keys:
            await self._repo.update(api_key.id, is_active=False)
            await self._audit_log(
                AuditAction.API_KEY_REVOKED,
                user_id=user_id,
                extra={
                    "key_name": api_key.name,
                    "key_prefix": api_key.key_prefix,
                    "reason": reason,
                },
            )

    async def authenticate(self, raw_key: str) -> APIKey:
        """Ham API key'i doğrular ve ilişkili APIKey nesnesini döndürür.

        Key'in formatını, hash'ini ve süresini kontrol eder. Başarılı
        doğrulamada ``last_used_at`` alanını günceller.

        Doğrulama adımları:
            1. Key prefix formatı kontrolü (sk_live_)
            2. Prefix ile eşleşen aktif key'leri bul
            3. Secret kısmını hash ile karşılaştır
            4. Süre dolumu kontrolü

        Args:
            raw_key: Doğrulanacak ham API key string'i.
                Format: ``sk_live_<80_hex_karakter>``

        Returns:
            APIKey: Doğrulanmış API key nesnesi.

        Raises:
            AuthenticationError: Key formatı geçersiz, key bulunamadı,
                hash eşleşmedi veya key süresi dolmuş.

        Note:
            ``last_used_at`` güncellemesi başarısız olsa bile
            doğrulama başarılı sayılır (non-blocking).
        """
        if not raw_key.startswith(settings.API_KEY_PREFIX):
            _logger.warning(
                "api_key_invalid_format", prefix=raw_key[:12] if len(raw_key) >= 12 else "short"
            )
            raise AuthenticationError("Geçersiz API key formatı.")

        prefix, secret_part = _split_key(raw_key)
        candidates = await self._repo.get_active_by_prefix(prefix)

        for api_key in candidates:
            if not verify_password(secret_part, api_key.key_hash):
                continue

            # last_used_at güncelle (non-blocking — hata fırlatmaz)
            with contextlib.suppress(Exception):
                await self._repo.update(api_key.id, last_used_at=datetime.now(UTC))

            await self._audit_log(
                AuditAction.API_KEY_USED,
                user_id=api_key.user_id,
                extra={"key_prefix": api_key.key_prefix},
            )
            return api_key

        _logger.warning("api_key_auth_failed", prefix=prefix)
        raise AuthenticationError("Geçersiz API key.")
