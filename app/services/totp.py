"""
TOTPService — TOTP tabanlı 2FA yönetimi.

Sorumluluklar: setup · verify (aktif et) · disable · login doğrulaması · backup kodlar
Sırlar Fernet ile şifrelenmiş hâlde DB'de saklanır.
"""

from __future__ import annotations

import base64
import io
import secrets
from typing import TYPE_CHECKING

import pyotp
import qrcode
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.exceptions import AuthenticationError, BusinessRuleError, TOTPNotConfiguredError
from app.core.redis import get_redis_client
from app.core.security import hash_password, verify_password
from app.db.repositories.totp_backup_code import TOTPBackupCodeRepository
from app.db.repositories.user import UserRepository
from app.services._keys import TOTP_BACKUP_KEY

if TYPE_CHECKING:
    from uuid import UUID as _UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models.user import User

_BACKUP_CODE_COUNT = 8
_BACKUP_CODE_TTL = 30 * 24 * 60 * 60  # 30 gün


def _get_fernet() -> Fernet:
    """SECRET_KEY'den Fernet anahtarı türet (ilk 32 byte, base64url encode)."""
    raw = settings.SECRET_KEY.encode()[:32].ljust(32, b"\x00")
    key = base64.urlsafe_b64encode(raw)
    return Fernet(key)


def _encrypt(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def _decrypt(ciphertext: str) -> str:
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as e:
        raise AuthenticationError("TOTP secret çözümlenemedi.") from e


def _generate_backup_codes() -> list[str]:
    """8 adet 8 karakterlik tek kullanımlık backup kodu üret."""
    return [secrets.token_hex(4).upper() for _ in range(_BACKUP_CODE_COUNT)]


class TOTPService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = UserRepository(session)
        self._backup_repo = TOTPBackupCodeRepository(session)

    async def setup(self, user: User) -> dict[str, str]:
        """
        Yeni TOTP secret üret, QR kodu döndür.
        Henüz aktif etmez — kullanıcı verify() ile onaylamalı.
        """
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)

        issuer = settings.APP_NAME
        label = f"{issuer}:{user.email}"
        provisioning_uri = totp.provisioning_uri(name=label, issuer_name=issuer)

        # QR kodu base64 PNG olarak üret
        img = qrcode.make(provisioning_uri)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        qr_b64 = base64.b64encode(buffer.getvalue()).decode()

        # Secret'ı şifrele, DB'ye geçici olarak kaydet (totp_enabled=False)
        await self._repo.update(user.id, totp_secret=_encrypt(secret), totp_enabled=False)

        return {
            "secret": secret,
            "qr_code": f"data:image/png;base64,{qr_b64}",
            "provisioning_uri": provisioning_uri,
        }

    async def verify_and_enable(self, user: User, code: str) -> list[str]:
        """
        Verilen TOTP kodunu doğrula ve 2FA'yı aktif et.
        Backup kodları döndürür (sadece bir kez gösterilir).
        """
        if not user.totp_secret:
            raise TOTPNotConfiguredError()

        secret = _decrypt(user.totp_secret)
        totp = pyotp.TOTP(secret)
        if not totp.verify(code, valid_window=1):
            raise AuthenticationError("Geçersiz doğrulama kodu.")

        await self._repo.update(user.id, totp_enabled=True)

        backup_codes = _generate_backup_codes()
        await self._persist_backup_codes(user.id, backup_codes)
        return backup_codes

    async def disable(self, user: User, code: str) -> None:
        """TOTP kodunu doğrulayarak 2FA'yı kapat."""
        if not user.totp_enabled or not user.totp_secret:
            raise BusinessRuleError("2FA zaten devre dışı.")

        if not await self._check_code(user, code):
            raise AuthenticationError("Geçersiz doğrulama kodu.")

        await self._repo.update(user.id, totp_secret=None, totp_enabled=False)

        redis = await get_redis_client()
        await redis.delete(TOTP_BACKUP_KEY.format(str(user.id)))
        await self._backup_repo.delete_all_for_user(user.id)

    async def check_login(self, user: User, code: str) -> None:
        """
        Login sırasında TOTP kodunu doğrula.
        Geçersizse AuthenticationError fırlatır.
        """
        if not await self._check_code(user, code):
            raise AuthenticationError("Geçersiz 2FA kodu.")

    async def _check_code(self, user: User, code: str) -> bool:
        """TOTP kodu veya backup kodu kabul eder."""
        if not user.totp_secret:
            return False

        secret = _decrypt(user.totp_secret)
        totp = pyotp.TOTP(secret)

        # Normal TOTP kodu
        if totp.verify(code, valid_window=1):
            return True

        # Backup kodu denemesi
        return await self._try_backup_code(str(user.id), code.upper())

    async def _try_backup_code(self, user_id: str, code: str) -> bool:
        """Backup kodu doğrula: önce Redis (hızlı yol), sonra DB fallback."""
        from uuid import UUID

        redis = await get_redis_client()
        key = TOTP_BACKUP_KEY.format(user_id)
        if await redis.sismember(key, code):
            await redis.srem(key, code)
            await self._mark_db_backup_code_used(UUID(user_id), code)
            return True
        # Redis TTL dolmuşsa DB'den kontrol et
        return await self._try_backup_code_from_db(UUID(user_id), code)

    async def _mark_db_backup_code_used(self, user_id: _UUID, code: str) -> None:
        """Redis hit durumunda DB kaydını da kullanılmış olarak işaretle."""
        active_codes = await self._backup_repo.get_active_codes(user_id)
        for db_code in active_codes:
            if verify_password(code, db_code.code_hash):
                await self._backup_repo.mark_used(db_code.id)
                return

    async def _try_backup_code_from_db(self, user_id: _UUID, code: str) -> bool:
        """Redis miss durumunda DB'deki hash'lerle karşılaştır (bcrypt)."""
        active_codes = await self._backup_repo.get_active_codes(user_id)
        for db_code in active_codes:
            if verify_password(code, db_code.code_hash):
                await self._backup_repo.mark_used(db_code.id)
                return True
        return False

    async def _persist_backup_codes(self, user_id: _UUID, codes: list[str]) -> None:
        """Backup kodları Redis'e (TTL'li set) ve DB'ye (bcrypt hash) yazar."""
        redis = await get_redis_client()
        key = TOTP_BACKUP_KEY.format(str(user_id))
        await redis.delete(key)
        await redis.sadd(key, *codes)
        await redis.expire(key, _BACKUP_CODE_TTL)

        await self._backup_repo.delete_all_for_user(user_id)
        for code in codes:
            await self._backup_repo.create(
                user_id=user_id,
                code_hash=hash_password(code),
                is_used=False,
            )

    async def regenerate_backup_codes(self, user: User, totp_code: str) -> list[str]:
        """
        Geçerli TOTP kodu doğrulanarak backup kodları yeniden üretir.
        Eski kodlar geçersiz olur.
        """
        if not user.totp_enabled or not user.totp_secret:
            raise TOTPNotConfiguredError()
        if not await self._check_code(user, totp_code):
            raise AuthenticationError("Geçersiz doğrulama kodu.")
        new_codes = _generate_backup_codes()
        await self._persist_backup_codes(user.id, new_codes)
        return new_codes

    async def get_backup_code_count(self, user: User) -> int:
        """Kullanılmamış backup kod sayısını döndürür."""
        if not user.totp_enabled:
            raise TOTPNotConfiguredError()
        return await self._backup_repo.count_active(user.id)
