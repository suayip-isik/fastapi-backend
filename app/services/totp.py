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

from app.core.config import settings
from app.core.exceptions import AuthenticationError, BusinessRuleError, TOTPNotConfiguredError
from app.core.redis import get_redis_client
from app.core.security import decrypt_secret, encrypt_secret, hash_password, verify_password
from app.db.repositories.totp_backup_code import TOTPBackupCodeRepository
from app.db.repositories.user import UserRepository
from app.services._keys import TOTP_BACKUP_KEY

if TYPE_CHECKING:
    from uuid import UUID as _UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models.user import User

_BACKUP_CODE_COUNT = 8
_BACKUP_CODE_TTL = 30 * 24 * 60 * 60  # 30 gün


def _generate_backup_codes() -> list[str]:
    """8 adet 8 karakterlik tek kullanımlık backup kodu üret."""
    return [secrets.token_hex(4).upper() for _ in range(_BACKUP_CODE_COUNT)]


class TOTPService:
    """TOTP tabanli iki faktorlu kimlik dogrulama servisidir."""

    def __init__(self, session: AsyncSession) -> None:
        """TOTPService nesnesini gerekli repository'lerle olusturur."""
        self._repo = UserRepository(session)
        self._backup_repo = TOTPBackupCodeRepository(session)

    async def setup(self, user: User) -> dict[str, str]:
        """Kullanıcı için TOTP 2FA kurulumunu başlatır.

        Yeni bir TOTP secret üretir ve kullanıcıya QR kod ile birlikte döndürür.
        Bu aşamada 2FA henüz aktif edilmez; kullanıcının verify_and_enable()
        metodu ile doğrulama yapması gerekir.

        Args:
            user: TOTP kurulumu yapılacak kullanıcı nesnesi.

        Returns:
            Aşağıdaki anahtarları içeren sözlük:
                - secret: Base32 formatında TOTP secret (manuel giriş için).
                - qr_code: Base64 kodlanmış PNG QR kod (data URI formatında).
                - provisioning_uri: Authenticator uygulaması için otpauth:// URI.

        Note:
            Secret, Fernet ile şifrelenerek veritabanına kaydedilir.
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
        await self._repo.update(user.id, totp_secret=encrypt_secret(secret), totp_enabled=False)

        return {
            "secret": secret,
            "qr_code": f"data:image/png;base64,{qr_b64}",
            "provisioning_uri": provisioning_uri,
        }

    async def verify_and_enable(self, user: User, code: str) -> list[str]:
        """TOTP kodunu doğrulayarak 2FA'yı aktif eder.

        Kullanıcının authenticator uygulamasından girdiği kodu doğrular
        ve başarılı olursa 2FA'yı aktif eder. Ayrıca tek kullanımlık
        backup kodları oluşturur.

        Args:
            user: 2FA aktif edilecek kullanıcı nesnesi.
            code: Authenticator uygulamasından alınan 6 haneli TOTP kodu.

        Returns:
            8 adet tek kullanımlık backup kodu listesi. Bu kodlar sadece
            bir kez gösterilir ve kullanıcı tarafından güvenli bir yerde
            saklanmalıdır.

        Raises:
            TOTPNotConfiguredError: Kullanıcı için TOTP kurulumu yapılmamışsa.
            AuthenticationError: Girilen TOTP kodu geçersizse.

        Note:
            Backup kodları hem Redis'e (hızlı erişim için) hem de veritabanına
            (bcrypt hash olarak) kaydedilir.
        """
        if not user.totp_secret:
            raise TOTPNotConfiguredError()

        secret = decrypt_secret(user.totp_secret)
        totp = pyotp.TOTP(secret)
        if not totp.verify(code, valid_window=1):
            raise AuthenticationError("Geçersiz doğrulama kodu.")

        await self._repo.update(user.id, totp_enabled=True)

        backup_codes = _generate_backup_codes()
        await self._persist_backup_codes(user.id, backup_codes)
        return backup_codes

    async def disable(self, user: User, code: str) -> None:
        """Kullanıcının 2FA'sını devre dışı bırakır.

        Güvenlik için mevcut TOTP kodunu doğruladıktan sonra 2FA'yı kapatır.
        TOTP secret ve tüm backup kodları silinir.

        Args:
            user: 2FA devre dışı bırakılacak kullanıcı nesnesi.
            code: Doğrulama için gerekli TOTP veya backup kodu.

        Raises:
            BusinessRuleError: 2FA zaten devre dışıysa.
            AuthenticationError: Girilen kod geçersizse.

        Note:
            İşlem sonrasında kullanıcının tekrar 2FA kurması için
            setup() metodunu çağırması gerekir.
        """
        if not user.totp_enabled or not user.totp_secret:
            raise BusinessRuleError("2FA zaten devre dışı.")

        if not await self._check_code(user, code):
            raise AuthenticationError("Geçersiz doğrulama kodu.")

        await self._repo.update(user.id, totp_secret=None, totp_enabled=False)

        redis = await get_redis_client()
        await redis.delete(TOTP_BACKUP_KEY.format(str(user.id)))
        await self._backup_repo.delete_all_for_user(user.id)

    async def check_login(self, user: User, code: str) -> None:
        """Login sırasında TOTP kodunu doğrular.

        Kullanıcı girişi sırasında ikinci faktör doğrulaması için kullanılır.
        Hem normal TOTP kodu hem de backup kodu kabul edilir.

        Args:
            user: Giriş yapan kullanıcı nesnesi.
            code: Kullanıcının girdiği TOTP veya backup kodu.

        Raises:
            AuthenticationError: Kod geçersizse veya süresi dolmuşsa.

        Example:
            >>> await totp_service.check_login(user, "123456")
        """
        if not await self._check_code(user, code):
            raise AuthenticationError("Geçersiz 2FA kodu.")

    async def _check_code(self, user: User, code: str) -> bool:
        """Verilen kodu TOTP veya backup kodu olarak doğrular.

        Önce normal TOTP doğrulaması yapılır (±1 pencere toleransıyla).
        Başarısız olursa backup kod olarak denenir.

        Args:
            user: Kod doğrulanacak kullanıcı nesnesi.
            code: Doğrulanacak TOTP veya backup kodu.

        Returns:
            Kod geçerliyse True, değilse False.
        """
        if not user.totp_secret:
            return False

        secret = decrypt_secret(user.totp_secret)
        totp = pyotp.TOTP(secret)

        # Normal TOTP kodu
        if totp.verify(code, valid_window=1):
            return True

        # Backup kodu denemesi
        return await self._try_backup_code(str(user.id), code.upper())

    async def _try_backup_code(self, user_id: str, code: str) -> bool:
        """Backup kodunu doğrular ve kullanılmış olarak işaretler.

        Performans için önce Redis'teki cache kontrol edilir. Redis'te
        bulunamazsa (TTL dolmuş olabilir) veritabanına fallback yapılır.

        Args:
            user_id: Kullanıcı UUID'si (string formatında).
            code: Doğrulanacak backup kodu (büyük harf).

        Returns:
            Kod geçerli ve kullanılmamışsa True, değilse False.

        Note:
            Başarılı doğrulamada kod hem Redis'ten hem DB'den silinir/işaretlenir.
        """
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
        """Veritabanındaki backup kodunu kullanılmış olarak işaretler.

        Redis'te bulunan bir backup kodu kullanıldığında, tutarlılık için
        veritabanındaki karşılık gelen kaydı da günceller.

        Args:
            user_id: Kullanıcı UUID'si.
            code: Kullanılan backup kodu (düz metin).
        """
        active_codes = await self._backup_repo.get_active_codes(user_id)
        for db_code in active_codes:
            if verify_password(code, db_code.code_hash):
                await self._backup_repo.mark_used(db_code.id)
                return

    async def _try_backup_code_from_db(self, user_id: _UUID, code: str) -> bool:
        """Redis cache miss durumunda veritabanından backup kodu doğrular.

        Aktif (kullanılmamış) backup kodlarını veritabanından çeker ve
        bcrypt hash karşılaştırması yapar.

        Args:
            user_id: Kullanıcı UUID'si.
            code: Doğrulanacak backup kodu (düz metin).

        Returns:
            Kod geçerli ve kullanılmamışsa True, değilse False.
        """
        active_codes = await self._backup_repo.get_active_codes(user_id)
        for db_code in active_codes:
            if verify_password(code, db_code.code_hash):
                await self._backup_repo.mark_used(db_code.id)
                return True
        return False

    async def _persist_backup_codes(self, user_id: _UUID, codes: list[str]) -> None:
        """Backup kodlarını Redis ve veritabanına kaydeder.

        Mevcut backup kodları silinir ve yenileri oluşturulur.
        Redis'te düz metin olarak (hızlı erişim için), veritabanında
        bcrypt hash olarak saklanır.

        Args:
            user_id: Kullanıcı UUID'si.
            codes: Kaydedilecek backup kodları listesi.

        Note:
            Redis'teki kodlar 30 günlük TTL ile saklanır.
        """
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
        """Yeni backup kodları oluşturur ve eskileri geçersiz kılar.

        Kullanıcı backup kodlarını kaybettiyse veya tükettiyse bu metot
        ile yeni kodlar alabilir. Güvenlik için mevcut TOTP kodu gereklidir.

        Args:
            user: Backup kodları yenilenecek kullanıcı nesnesi.
            totp_code: Doğrulama için gerekli TOTP veya mevcut backup kodu.

        Returns:
            8 adet yeni tek kullanımlık backup kodu listesi.

        Raises:
            TOTPNotConfiguredError: 2FA aktif değilse.
            AuthenticationError: Doğrulama kodu geçersizse.

        Warning:
            Eski backup kodları bu işlemden sonra kullanılamaz hâle gelir.
        """
        if not user.totp_enabled or not user.totp_secret:
            raise TOTPNotConfiguredError()
        if not await self._check_code(user, totp_code):
            raise AuthenticationError("Geçersiz doğrulama kodu.")
        new_codes = _generate_backup_codes()
        await self._persist_backup_codes(user.id, new_codes)
        return new_codes

    async def get_backup_code_count(self, user: User) -> int:
        """Kullanılmamış backup kod sayısını döndürür.

        Kullanıcının kalan backup kod sayısını kontrol etmek için kullanılır.
        Düşük sayıda backup kodu kaldığında kullanıcıya uyarı gösterilebilir.

        Args:
            user: Backup kod sayısı sorgulanacak kullanıcı nesnesi.

        Returns:
            Henüz kullanılmamış aktif backup kod sayısı (0-8 arası).

        Raises:
            TOTPNotConfiguredError: 2FA aktif değilse.
        """
        if not user.totp_enabled:
            raise TOTPNotConfiguredError()
        return await self._backup_repo.count_active(user.id)
