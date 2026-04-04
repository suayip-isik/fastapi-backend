"""
Health check modülü — DB, Redis ve Storage bağlantılarını test eder.
/health, /health/live ve /health/ready endpoint'leri için kullanılır.
"""

from __future__ import annotations

import aioboto3
from sqlalchemy import text

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import get_redis_client
from app.db.session import AsyncSessionFactory

logger = get_logger(__name__)


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
        - AsyncSessionFactory ile session oluşturulur ve otomatik kapatılır
        - Exception durumunda (False, error_message) döner (raise etmez)
        - Hata durumunda warning seviyesinde log kaydı oluşturulur
    """
    try:
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as e:
        logger.warning("health_db_failed", error=str(e))
        return False, str(e)


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
    try:
        client = await get_redis_client()
        await client.ping()
        return True, "ok"
    except Exception as e:
        logger.warning("health_redis_failed", error=str(e))
        return False, str(e)


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
    except Exception as e:
        logger.warning("health_storage_failed", error=str(e))
        return False, str(e)
