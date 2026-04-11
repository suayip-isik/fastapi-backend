"""TOTPBackupCodeRepository — backup kod CRUD işlemleri."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import delete, func, select, update

from app.db.models.totp_backup_code import TOTPBackupCode
from app.db.repositories.base import BaseRepository

if TYPE_CHECKING:
    from uuid import UUID


class TOTPBackupCodeRepository(BaseRepository[TOTPBackupCode]):
    """TOTP yedek kodlarına özgü veritabanı işlemlerini yöneten repository.

    BaseRepository[TOTPBackupCode] üzerine inşa edilmiştir. Genel CRUD
    işlemlerine ek olarak aktif (kullanılmamış) kod sorgulama, sayma,
    kullanıldı işaretleme ve toplu silme gibi TOTP iş mantığına özgü
    metotları içerir.

    Attributes:
        model: Bağlı SQLAlchemy modeli (TOTPBackupCode).

    Note:
        TOTPService, yedek kod üretimi ve doğrulaması için bu repository'yi kullanır.
    """

    model = TOTPBackupCode

    async def get_active_codes(self, user_id: UUID) -> list[TOTPBackupCode]:
        """Kullanıcının henüz kullanılmamış tüm yedek kodlarını döndürür.

        is_used=False olan tüm TOTPBackupCode kayıtlarını sırasız olarak getirir.
        TOTP doğrulama sırasında hangi kodların hâlâ geçerli olduğunu belirlemek
        için kullanılır.

        Args:
            user_id: Kodları sorgulanacak kullanıcının UUID'si.

        Returns:
            Kullanılmamış TOTPBackupCode nesnelerinin listesi.
            Kullanıcının hiç aktif kodu yoksa boş liste döner.

        Example:
            >>> codes = await repo.get_active_codes(user.id)
            >>> for code in codes:
            ...     if verify_hash(input_code, code.code_hash):
            ...         await repo.mark_used(code.id)
            ...         break
        """
        result = await self._session.execute(
            select(TOTPBackupCode).where(
                TOTPBackupCode.user_id == user_id,
                TOTPBackupCode.is_used.is_(False),
            )
        )
        return list(result.scalars().all())

    async def count_active(self, user_id: UUID) -> int:
        """Kullanıcının kullanılmamış yedek kod sayısını döndürür.

        Tek bir COUNT sorgusu çalıştırır; tüm kodları belleğe çekmeden sayı döner.
        Kullanıcıya kalan yedek kod adedini göstermek için kullanılır.

        Args:
            user_id: Aktif kod sayısı sorgulanacak kullanıcının UUID'si.

        Returns:
            Kullanılmamış (is_used=False) kod sayısı. Hiç yoksa 0 döner.

        Example:
            >>> remaining = await repo.count_active(user.id)
            >>> if remaining < 3:
            ...     notify_user("Yedek kodlarınız azalıyor.")
        """
        result = await self._session.execute(
            select(func.count())
            .select_from(TOTPBackupCode)
            .where(
                TOTPBackupCode.user_id == user_id,
                TOTPBackupCode.is_used.is_(False),
            )
        )
        return result.scalar_one()

    async def mark_used(self, code_id: UUID) -> None:
        """Belirtilen yedek kodu kullanılmış olarak işaretler.

        is_used=True ve used_at=şimdiki UTC zamanı olarak günceller.
        Başarılı bir backup kod girişinin ardından çağrılır.

        Args:
            code_id: Kullanıldı olarak işaretlenecek TOTPBackupCode kaydının UUID'si.

        Note:
            - Bu işlem geri alınamaz; kod bir kez kullanıldı işaretlenince tekrar kullanılamaz.
            - Session commit'i çağıran servis katmanına aittir.
        """
        await self._session.execute(
            update(TOTPBackupCode)
            .where(TOTPBackupCode.id == code_id)
            .values(is_used=True, used_at=datetime.now(UTC))
        )

    async def delete_all_for_user(self, user_id: UUID) -> None:
        """Kullanıcıya ait tüm yedek kodları kalıcı olarak siler.

        Hem kullanılmış hem kullanılmamış tüm TOTPBackupCode kayıtlarını siler.
        Yeni kod seti üretilmeden önce (regenerate) veya TOTP devre dışı
        bırakılırken (disable) eski kodları temizlemek için çağrılır.

        Args:
            user_id: Yedek kodları silinecek kullanıcının UUID'si.

        Note:
            - Silme işlemi toplu (bulk DELETE) gerçekleştirilir.
            - Session commit'i çağıran servis katmanına aittir.
        """
        await self._session.execute(delete(TOTPBackupCode).where(TOTPBackupCode.user_id == user_id))
