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
    """PostgreSQL bağlantısını SELECT 1 ile doğrula."""
    try:
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as e:
        logger.warning("health_db_failed", error=str(e))
        return False, str(e)


async def check_redis() -> tuple[bool, str]:
    """Redis bağlantısını PING ile doğrula."""
    try:
        client = await get_redis_client()
        await client.ping()
        return True, "ok"
    except Exception as e:
        logger.warning("health_redis_failed", error=str(e))
        return False, str(e)


async def check_storage() -> tuple[bool, str]:
    """S3/MinIO bucket erişimini doğrula."""
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
