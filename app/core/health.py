"""
Health check modülü — DB, Redis ve Storage bağlantılarını test eder.
/health, /health/live ve /health/ready endpoint'leri için kullanılır.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import aioboto3
from botocore.exceptions import BotoCoreError, ClientError
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.adapters.infrastructure import RedisAdapter
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session_provider import get_default_session_factory

if TYPE_CHECKING:
    from app.ports.infrastructure import RedisPort

logger = get_logger(__name__)


def _probe_failure(probe: str, exc: Exception) -> tuple[bool, str]:
    """External health probe hatalarını normalize et."""
    logger.warning("health_probe_failed", probe=probe, error=str(exc))
    return False, str(exc)


class DatabaseHealthProbe:
    """DB health probe adapter'ı."""

    async def check(self) -> tuple[bool, str]:
        try:
            await _run_database_probe()
            return True, "ok"
        except (SQLAlchemyError, OSError) as exc:
            return _probe_failure("db", exc)
        except Exception as exc:
            return _probe_failure("db", exc)


class RedisHealthProbe:
    """Redis health probe adapter'ı."""

    def __init__(self, redis: RedisPort | None = None) -> None:
        self._redis = redis or RedisAdapter()

    async def check(self) -> tuple[bool, str]:
        try:
            await self._redis.ping()
            return True, "ok"
        except (RedisError, OSError) as exc:
            return _probe_failure("redis", exc)
        except Exception as exc:
            return _probe_failure("redis", exc)


class StorageHealthProbe:
    """Object storage health probe adapter'ı."""

    async def check(self) -> tuple[bool, str]:
        try:
            session = aioboto3.Session(
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
                region_name=settings.S3_REGION,
            )
            endpoint = settings.S3_ENDPOINT_URL or None
            async with session.client("s3", endpoint_url=endpoint) as s3:
                await s3.head_bucket(Bucket=settings.S3_BUCKET_NAME)
            return True, "ok"
        except (BotoCoreError, ClientError, OSError) as exc:
            return _probe_failure("storage", exc)
        except Exception as exc:
            return _probe_failure("storage", exc)


async def _run_database_probe() -> None:
    """DB probe sorgusunu çalıştır."""
    session_factory = get_default_session_factory()
    async with session_factory() as session:
        await session.execute(text("SELECT 1"))


async def check_database() -> tuple[bool, str]:
    """PostgreSQL veritabanı bağlantısını kontrol eder.

    Basit bir SELECT 1 sorgusu çalıştırarak DB erişilebilirliğini test eder.
    Kubernetes liveness/readiness probe'ları için kullanılır.

    Returns:
        tuple[bool, str]: İlk eleman sağlık durumu (True=sağlıklı, False=hata),
            ikinci eleman durum mesajı ("ok" veya hata detayı)

    Example:
        >>> is_healthy, message = await check_database()
        >>> # (True, "ok")

    Note:
        - Varsayılan session provider ile probe session'ı oluşturulur
        - Exception durumunda (False, error_message) döner (raise etmez)
        - Hata durumunda warning seviyesinde log kaydı oluşturulur
    """
    return await DatabaseHealthProbe().check()


async def check_redis() -> tuple[bool, str]:
    """Redis bağlantısını kontrol eder.

    PING komutu ile Redis sunucusuna erişilebilirliği test eder.
    Rate limiting ve ARQ task queue için Redis bağlantısının sağlıklı
    olduğunu doğrular.

    Returns:
        tuple[bool, str]: İlk eleman sağlık durumu (True=sağlıklı, False=hata),
            ikinci eleman durum mesajı ("ok" veya hata detayı)

    Example:
        >>> is_healthy, message = await check_redis()
        >>> # (True, "ok")

    Note:
        - get_redis_client() ile Redis client alınır
        - PING komutu başarısızsa False döner
        - Exception durumunda warning seviyesinde log kaydı oluşturulur
    """
    return await RedisHealthProbe().check()


async def check_storage() -> tuple[bool, str]:
    """S3/MinIO object storage bağlantısını kontrol eder.

    head_bucket operasyonu ile bucket'a erişilebilirliği test eder.
    File upload/download işlemleri için storage sisteminin sağlıklı
    olduğunu doğrular. Hem AWS S3 hem de MinIO (local dev) desteklenir.

    Returns:
        tuple[bool, str]: İlk eleman sağlık durumu (True=sağlıklı, False=hata),
            ikinci eleman durum mesajı ("ok" veya hata detayı)

    Example:
        >>> is_healthy, message = await check_storage()
        >>> # (True, "ok")

    Note:
        - aioboto3 Session ile S3 client oluşturulur
        - Settings'den S3_ACCESS_KEY, S3_SECRET_KEY, S3_REGION alınır
        - MinIO için S3_ENDPOINT_URL kullanılır
        - Bucket mevcut değilse veya erişim yoksa False döner
        - Exception durumunda warning seviyesinde log kaydı oluşturulur
    """
    return await StorageHealthProbe().check()
