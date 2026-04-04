"""
ARQ background task'ları.
Redis-based, async, lightweight — Celery'ye göre daha sade.
"""

from __future__ import annotations

import asyncio
from typing import Any

from arq import create_pool, cron
from arq.connections import ArqRedis, RedisSettings

from app.core.config import settings
from app.core.email import send_email
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Redis Settings ────────────────────────────────────────────────────────────


def get_redis_settings() -> RedisSettings:
    """ARQ worker için Redis bağlantı ayarlarını döndürür.

    Returns:
        RedisSettings: ARQ worker'ın kullanacağı Redis bağlantı konfigürasyonu.

    Note:
        - Ayarlar app.core.config.settings'ten okunur
        - Password None ise Redis authentication kapalı demektir
    """
    return RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD or None,
        database=settings.REDIS_DB,
    )


# ── Task Functions ────────────────────────────────────────────────────────────


async def send_welcome_email(ctx: dict[str, Any], user_id: str, email: str) -> dict[str, Any]:
    """Yeni kullanıcıya hoş geldiniz emaili gönderir (background task).

    Kayıt sonrası ARQ worker tarafından çalıştırılır. HTML formatlı
    email ile kullanıcıya platform hakkında bilgi ve giriş linki gönderilir.

    Args:
        ctx: ARQ worker context (DB, Redis vb. bağlantılar)
        user_id: Kullanıcı UUID (string formatında)
        email: Hedef email adresi

    Returns:
        Dict içinde gönderim durumu ve kullanıcı ID'si.

    Note:
        - SMTP hatası durumunda ARQ otomatik retry yapar
        - Email template inline HTML olarak oluşturulur
        - APP_URL ve APP_NAME ayarları config'den gelir

    Example:
        >>> # Endpoint'te enqueue edilir:
        >>> await enqueue(send_welcome_email, user_id=str(user.id), email=user.email)
    """
    logger.info("sending_welcome_email", user_id=user_id, email=email)
    try:
        login_url = settings.APP_URL
        await send_email(
            to=email,
            subject=f"{settings.APP_NAME}'a hoş geldiniz!",
            html_body=(
                f"<p>Merhaba,</p>"
                f"<p><strong>{settings.APP_NAME}</strong>'a hoş geldiniz! "
                f"Hesabınız başarıyla oluşturuldu.</p>"
                f"<p>Giriş yapmak için <a href='{login_url}'>tıklayın</a>.</p>"
            ),
        )
    except Exception as exc:
        logger.error("welcome_email_failed", user_id=user_id, error=str(exc))
        raise
    logger.info("welcome_email_sent", user_id=user_id)
    return {"status": "sent", "user_id": user_id}


async def process_file_upload(ctx: dict[str, Any], file_key: str, user_id: str) -> dict[str, Any]:
    """Upload edilen dosyayı background'da işler.

    Dosya yükleme sonrası thumbnail oluşturma, virus tarama, metadata
    çıkarma gibi işlemleri yapar. Şu an placeholder olarak çalışıyor.

    Args:
        ctx: ARQ worker context
        file_key: Storage'daki dosya anahtarı (S3/MinIO key)
        user_id: Dosyayı yükleyen kullanıcı ID'si

    Returns:
        dict[str, Any]: Status ve file_key içeren sonuç

    Note:
        - Gelecekte thumbnail resize, EXIF extraction eklenebilir
        - Virus tarama için ClamAV entegrasyonu düşünülebilir
    """
    logger.info("processing_upload", file_key=file_key, user_id=user_id)
    await asyncio.sleep(0.1)  # Simulate processing
    return {"status": "processed", "file_key": file_key}


async def send_verification_email(ctx: dict[str, Any], email: str, token: str) -> dict[str, Any]:
    """Email doğrulama linki içeren email gönderir (background task).

    Kullanıcı kaydı veya email değişikliği sonrası ARQ worker tarafından
    çalıştırılır. Token içeren doğrulama linki ile HTML email gönderir.

    Args:
        ctx: ARQ worker context (DB, Redis vb. bağlantılar)
        email: Doğrulanacak email adresi
        token: JWT doğrulama token'ı (24 saat geçerli)

    Returns:
        Dict içinde gönderim durumu ve email adresi.

    Note:
        - Token verify-email endpoint'inde doğrulanır
        - Link 24 saat geçerlidir (token TTL)
        - Token Redis'te email_verify:* prefix ile saklanır
        - SMTP hatası durumunda ARQ otomatik retry yapar

    Example:
        >>> # Auth service'te enqueue edilir:
        >>> token = create_verification_token(user.email)
        >>> await enqueue(send_verification_email, email=user.email, token=token)
    """
    logger.info("sending_verification_email", email=email)
    try:
        verify_url = f"{settings.APP_URL}/api/v1/auth/verify-email?token={token}"
        await send_email(
            to=email,
            subject="E-posta adresinizi doğrulayın",
            html_body=(
                f"<p>Hesabınızı doğrulamak için "
                f"<a href='{verify_url}'>buraya tıklayın</a>.</p>"
                f"<p>Bu link 24 saat geçerlidir.</p>"
            ),
        )
    except Exception as exc:
        logger.error("verification_email_failed", email=email, error=str(exc))
        raise
    logger.info("verification_email_sent", email=email)
    return {"status": "sent", "email": email}


async def send_password_reset_email(ctx: dict[str, Any], email: str, token: str) -> dict[str, Any]:
    """Şifre sıfırlama linki içeren email gönderir (background task).

    Şifre sıfırlama talebi sonrası ARQ worker tarafından çalıştırılır.
    Token içeren sıfırlama linki ile HTML email gönderir.

    Args:
        ctx: ARQ worker context (DB, Redis vb. bağlantılar)
        email: Şifresi sıfırlanacak kullanıcının email adresi
        token: JWT sıfırlama token'ı (15 dakika geçerli)

    Returns:
        Dict içinde gönderim durumu ve email adresi.

    Note:
        - Token reset-password endpoint'inde kullanılır
        - Link 15 dakika geçerlidir (token TTL)
        - Token Redis'te password_reset:* prefix ile saklanır
        - SMTP hatası durumunda ARQ otomatik retry yapar
        - Güvenlik: Token tek kullanımlık (kullanıldıktan sonra silinir)

    Example:
        >>> # Auth endpoint'te enqueue edilir:
        >>> token = create_password_reset_token(user.email)
        >>> await enqueue(send_password_reset_email, email=user.email, token=token)
    """
    logger.info("sending_password_reset_email", email=email)
    try:
        reset_url = f"{settings.APP_URL}/api/v1/auth/reset-password?token={token}"
        await send_email(
            to=email,
            subject="Şifre sıfırlama isteği",
            html_body=(
                f"<p>Şifrenizi sıfırlamak için "
                f"<a href='{reset_url}'>buraya tıklayın</a>.</p>"
                f"<p>Bu link 15 dakika geçerlidir.</p>"
            ),
        )
    except Exception as exc:
        logger.error("password_reset_email_failed", email=email, error=str(exc))
        raise
    logger.info("password_reset_email_sent", email=email)
    return {"status": "sent", "email": email}


async def cleanup_expired_tokens(ctx: dict[str, Any]) -> dict[str, Any]:
    """TTL'siz kalan orphaned Redis key'lerini temizler (cron job).

    Her gece yarısı otomatik çalışır. Blacklist, email verification,
    password reset ve OAuth state key'lerinden TTL'si olmayan
    (orphaned) olanları bulup siler.

    Args:
        ctx: ARQ worker context

    Returns:
        dict[str, Any]: Temizlenen key sayısını içeren sonuç

    Note:
        - Cron schedule: Her gün 00:00
        - Kontrol edilen pattern'ler: blacklist:*, email_verify:*,
          password_reset:*, oauth_state:*
        - TTL -1 olan key'ler (hiç expire olmayan) temizlenir
        - Batch size: 100 (SCAN komutu ile)
    """
    logger.info("cleaning_orphaned_redis_keys")
    from app.core.redis import get_redis_client

    redis = await get_redis_client()
    prefixes = ["blacklist:*", "email_verify:*", "password_reset:*", "oauth_state:*"]
    cleaned = 0
    for pattern in prefixes:
        cursor: int = 0
        while True:
            cursor, keys = await redis.scan(cursor, match=pattern, count=100)
            for key in keys:
                ttl = await redis.ttl(key)
                if ttl == -1:  # TTL yok — orphaned key
                    await redis.delete(key)
                    cleaned += 1
            if cursor == 0:
                break
    logger.info("expired_tokens_cleaned", count=cleaned)
    return {"status": "cleaned", "count": cleaned}


# ── Worker Config ─────────────────────────────────────────────────────────────


class WorkerSettings:
    """ARQ worker yapılandırma ayarları.

    Background task fonksiyonlarını, cron job'ları, Redis bağlantı ayarlarını
    ve worker limitlerini tanımlar. ARQ worker başlatılırken kullanılır.

    Attributes:
        functions: Worker'da çalışacak task fonksiyonlarının listesi.
        cron_jobs: Zamanlanmış cron job'lar (cleanup gibi).
        redis_settings: Redis bağlantı konfigürasyonu.
        max_jobs: Aynı anda çalışabilecek maksimum job sayısı.
        job_timeout: Bir job'ın maksimum çalışma süresi (saniye).

    Example:
        >>> # Worker'ı başlatmak için:
        >>> # python -m arq app.tasks.worker.WorkerSettings

    Note:
        cleanup_expired_tokens her gece saat 00:00'da otomatik çalışır.
    """

    functions = [
        send_welcome_email,
        process_file_upload,
        cleanup_expired_tokens,
        send_verification_email,
        send_password_reset_email,
    ]

    # Cron jobs
    cron_jobs: list[Any] = [
        cron(cleanup_expired_tokens, hour=0, minute=0),  # Her gece yarısı token temizliği
    ]

    redis_settings = get_redis_settings()

    max_jobs = 10
    job_timeout = 300  # 5 dakika


# ── Pool Helper ───────────────────────────────────────────────────────────────

_arq_pool: ArqRedis | None = None


async def get_task_queue() -> ArqRedis:
    """ARQ task queue pool'unu döndürür.

    FastAPI Depends() ile dependency injection için kullanılır.
    Singleton pattern ile tek bir pool instance'ı paylaşılır.

    Returns:
        ArqRedis: ARQ Redis connection pool

    Note:
        - İlk çağrıda pool oluşturulur (lazy initialization)
        - Sonraki çağrılarda aynı pool döndürülür (singleton)
    """
    global _arq_pool
    if _arq_pool is None:
        _arq_pool = await create_pool(get_redis_settings())
    return _arq_pool


async def enqueue(task_func: Any, *args: Any, **kwargs: Any) -> None:
    """Background task'ı kuyruğa ekler.

    Helper fonksiyon. Task fonksiyonunu ve parametrelerini alarak
    ARQ kuyruğuna job olarak ekler.

    Args:
        task_func: Çalıştırılacak async task fonksiyonu
        *args: Task fonksiyonuna gönderilecek pozisyonel argümanlar
        **kwargs: Task fonksiyonuna gönderilecek keyword argümanlar

    Example:
        ```python
        await enqueue(send_welcome_email, user_id="123", email="user@example.com")
        ```

    Note:
        - Task function'ın adı ARQ'ya string olarak iletilir
        - Worker'ın WorkerSettings.functions listesinde tanımlı olmalı
    """
    pool = await get_task_queue()
    await pool.enqueue_job(task_func.__name__, *args, **kwargs)
