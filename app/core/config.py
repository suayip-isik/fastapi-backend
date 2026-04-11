"""
Core configuration — tüm ayarlar tek yerden yönetilir.
Pydantic Settings ile .env dosyasından otomatik yüklenir.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import AnyHttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Uygulama yapılandırma ayarlarını yöneten merkezi settings sınıfı.

    .env dosyasından environment variable'ları okur ve Pydantic validation
    ile type-safe ayarlar sağlar. Tüm uygulama genelinde tek bir settings
    instance kullanılır (@lru_cache ile).

    Bu sınıf şunları yönetir:
    - Uygulama temel ayarları (isim, versiyon, debug modu)
    - Veritabanı bağlantı bilgileri (PostgreSQL)
    - Cache ve task queue (Redis)
    - Güvenlik (JWT)
    - Dosya yükleme ve storage (MinIO/S3)
    - Email gönderimi (SMTP)
    - Rate limiting kuralları
    - Logging ve monitoring (Sentry)

    Attributes:
        APP_NAME: Uygulama adı
        APP_ENV: Ortam (development, staging, production)
        APP_DEBUG: Debug modunun aktif olup olmadığı
        DATABASE_URL: PostgreSQL bağlantı URL'i (property ile oluşturulur)
        REDIS_URL: Redis bağlantı URL'i (property ile oluşturulur)
        JWT_PRIVATE_KEY: RSA private key (property ile okunur)
        JWT_PUBLIC_KEY: RSA public key (property ile okunur)

    Note:
        - Production ortamında SECRET_KEY, ADMIN_PASSWORD güvenli değerler olmalı
        - Production'da APP_DEBUG=False zorunludur
        - JWT key dosyaları keys/ klasöründe olmalı (private.pem, public.pem)
        - CORS_ORIGINS ve ALLOWED_UPLOAD_TYPES JSON array formatında verilmeli

    Example:
        >>> from app.core.config import settings
        >>> settings.APP_NAME
        'FastAPI App'
        >>> settings.DATABASE_URL
        'postgresql+asyncpg://user:pass@localhost:5432/mydb'
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "FastAPI App"
    APP_ENV: str = "development"
    APP_DEBUG: bool = False
    APP_VERSION: str = "1.0.0"
    APP_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"
    SECRET_KEY: str
    ALLOWED_HOSTS: list[str] = ["*"]
    CORS_ORIGINS: list[AnyHttpUrl | str] = []

    # ── Database ─────────────────────────────────────────────────────────────
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    @property
    def DATABASE_URL(self) -> str:
        """PostgreSQL veritabanı bağlantı URL'ini oluşturur.

        asyncpg driver ile asenkron bağlantı için PostgreSQL+asyncpg://
        formatında URL döner. SQLAlchemy async session'lar bu URL'i kullanır.

        Returns:
            Tam veritabanı bağlantı URL'i (kullanıcı, şifre, host, port, db adı ile)

        Example:
            >>> settings.DATABASE_URL
            'postgresql+asyncpg://user:pass@localhost:5432/dbname'
        """
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Alembic migration'ları için senkron PostgreSQL bağlantı URL'i.

        psycopg2 driver kullanarak senkron bağlantı sağlar. Alembic
        migration script'leri bu URL'i kullanır çünkü async desteği yoktur.

        Returns:
            Senkron veritabanı bağlantı URL'i (psycopg2 driver ile)

        Note:
            Sadece Alembic migration'ları için kullanılır.
            Uygulama içinde DATABASE_URL (async) kullanılmalıdır.

        Example:
            >>> settings.DATABASE_URL_SYNC
            'postgresql+psycopg2://user:pass@localhost:5432/dbname'
        """
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    @property
    def REDIS_URL(self) -> str:
        """Redis bağlantı URL'ini oluşturur.

        Redis cache ve ARQ task queue için kullanılan bağlantı URL'i.
        Şifre varsa authentication bilgisi dahil edilir.

        Returns:
            Redis bağlantı URL'i (redis://[password@]host:port/db formatında)

        Note:
            REDIS_PASSWORD boşsa authentication olmadan bağlanır (local dev için).
            Production'da mutlaka şifre ayarlanmalıdır.

        Example:
            >>> settings.REDIS_URL  # şifresiz
            'redis://localhost:6379/0'
            >>> settings.REDIS_URL  # şifreli
            'redis://:mypassword@localhost:6379/0'
        """
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ── JWT / Auth ────────────────────────────────────────────────────────────
    JWT_PRIVATE_KEY_PATH: Path = Path("./keys/private.pem")
    JWT_PUBLIC_KEY_PATH: Path = Path("./keys/public.pem")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── Cookie ────────────────────────────────────────────────────────────────
    COOKIE_DOMAIN: str | None = None
    COOKIE_SECURE: bool = True
    COOKIE_SAMESITE: str = "lax"
    COOKIE_PATH: str = "/"

    @property
    def JWT_PRIVATE_KEY(self) -> str:
        """JWT token imzalama için RSA private key'i okur.

        keys/private.pem dosyasından private key içeriğini okur.
        Access ve refresh token'ları imzalamak için kullanılır.

        Returns:
            PEM formatında RSA private key içeriği

        Raises:
            FileNotFoundError: Private key dosyası bulunamazsa

        Note:
            Private key asla versiyon kontrolüne eklenmemeli.
            Production'da güvenli bir yerde saklanmalıdır.

        Example:
            >>> settings.JWT_PRIVATE_KEY[:26]
            '-----BEGIN PRIVATE KEY-----'
        """
        return self.JWT_PRIVATE_KEY_PATH.read_text()

    @property
    def JWT_PUBLIC_KEY(self) -> str:
        """JWT token doğrulama için RSA public key'i okur.

        keys/public.pem dosyasından public key içeriğini okur.
        Token imzalarını doğrulamak için kullanılır.

        Returns:
            PEM formatında RSA public key içeriği

        Raises:
            FileNotFoundError: Public key dosyası bulunamazsa

        Note:
            Public key private key'den türetilir ve paylaşılabilir.
            Token doğrulama sadece public key ile yapılır.

        Example:
            >>> settings.JWT_PUBLIC_KEY[:25]
            '-----BEGIN PUBLIC KEY-----'
        """
        return self.JWT_PUBLIC_KEY_PATH.read_text()

    # ── Storage ───────────────────────────────────────────────────────────────
    STORAGE_BACKEND: str = "minio"  # minio | s3 | local
    S3_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET_NAME: str = "app-uploads"
    S3_REGION: str = "us-east-1"
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_UPLOAD_TYPES: list[str] = ["image/jpeg", "image/png", "application/pdf"]

    @property
    def MAX_UPLOAD_SIZE_BYTES(self) -> int:
        """Maksimum dosya yükleme boyutunu byte cinsinden döner.

        MAX_UPLOAD_SIZE_MB değerini byte'a çevirir. File upload
        middleware ve endpoint'lerde dosya boyutu kontrolü için kullanılır.

        Returns:
            Maksimum yükleme boyutu (byte cinsinden)

        Example:
            >>> settings.MAX_UPLOAD_SIZE_MB = 10
            >>> settings.MAX_UPLOAD_SIZE_BYTES
            10485760  # 10 * 1024 * 1024
        """
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    # ── Email / SMTP ──────────────────────────────────────────────────────────
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM_EMAIL: str = "noreply@example.com"

    # ── Admin Seed ────────────────────────────────────────────────────────────
    ADMIN_EMAIL: str = "admin@example.com"
    ADMIN_PASSWORD: str = "changeme"

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    RATE_LIMIT_DEFAULT: str = "100/minute"
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_AUTH: str = "5/minute"  # login, reset-password
    RATE_LIMIT_AUTH_EMAIL: str = "3/hour"  # forgot-password, resend-verification
    RATE_LIMIT_REGISTER: str = "3/hour"  # register
    RATE_LIMIT_UPLOAD: str = "20/hour"
    RATE_LIMIT_API_KEYS: str = "20/minute"  # API key create/revoke

    # ── Token TTLs ────────────────────────────────────────────────────────────
    EMAIL_VERIFY_TTL: int = 86400  # 24 hours in seconds
    PASSWORD_RESET_TTL: int = 900  # 15 minutes in seconds
    LOGIN_PARTIAL_TTL: int = 300  # 5 minutes in seconds

    # ── Startup Guards ────────────────────────────────────────────────────────
    ENFORCE_DB_SCHEMA_CHECK: bool = True

    # ── Sentry ────────────────────────────────────────────────────────────────
    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1  # production için 0.1, dev için 1.0

    @field_validator("SENTRY_DSN", mode="before")
    @classmethod
    def _strip_sentry_dsn(cls, v: object) -> str:
        """SENTRY_DSN değerini temizler ve normalize eder.

        .env dosyasındaki inline comment'leri ve boşlukları temizler.
        Geçersiz DSN değerlerini boş string'e çevirir.

        Args:
            v: .env'den okunan ham değer

        Returns:
            Temizlenmiş Sentry DSN (geçerliyse) veya boş string

        Note:
            Bazı dotenv parser'lar inline comment (#) desteklemez.
            Bu validator # sonrasını otomatik olarak atar.
            Sadece http/https ile başlayan değerler kabul edilir.

        Example:
            >>> cls._strip_sentry_dsn("https://key@sentry.io/123 # comment")
            'https://key@sentry.io/123'
            >>> cls._strip_sentry_dsn("invalid-dsn")
            ''
        """
        if not isinstance(v, str):
            return ""
        # dotenv inline comment desteği olmadığında '#' sonrasını at
        cleaned = v.split("#")[0].strip()
        return cleaned if cleaned.startswith("http") else ""

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json | text

    # ── Validators ────────────────────────────────────────────────────────────
    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v: Any) -> list[Any]:
        """CORS_ORIGINS değerini parse eder.

        .env dosyasında JSON array formatındaki string'i Python list'e çevirir.
        Zaten list ise olduğu gibi döner.

        Args:
            v: .env'den okunan ham değer (string veya list)

        Returns:
            İzin verilen origin'lerin listesi

        Example:
            >>> cls.parse_cors('["http://localhost:3000", "https://app.com"]')
            ['http://localhost:3000', 'https://app.com']
        """
        if isinstance(v, str):
            result: list[Any] = json.loads(v)
            return result
        return list(v)

    @field_validator("ALLOWED_UPLOAD_TYPES", mode="before")
    @classmethod
    def parse_upload_types(cls, v: Any) -> list[Any]:
        """ALLOWED_UPLOAD_TYPES değerini parse eder.

        .env dosyasında JSON array formatındaki string'i Python list'e çevirir.
        İzin verilen MIME type'ların listesini döner.

        Args:
            v: .env'den okunan ham değer (string veya list)

        Returns:
            İzin verilen dosya MIME type'larının listesi

        Example:
            >>> cls.parse_upload_types('["image/jpeg", "image/png", "application/pdf"]')
            ['image/jpeg', 'image/png', 'application/pdf']
        """
        if isinstance(v, str):
            result: list[Any] = json.loads(v)
            return result
        return list(v)

    @model_validator(mode="after")
    def validate_production_settings(self) -> Settings:
        """Production ortamı için güvenlik validasyonları yapar.

        Production'da kritik güvenlik ayarlarının doğru yapılandırılmasını
        zorunlu tutar:
        - SECRET_KEY default değer olmamalı
        - DEBUG modu kapalı olmalı
        - ADMIN_PASSWORD güvenli olmalı

        Returns:
            Validate edilmiş Settings instance

        Raises:
            ValueError: Production'da güvenlik koşulları sağlanmazsa

        Note:
            Bu validasyon sadece APP_ENV="production" olduğunda çalışır.
            Development ve staging ortamları etkilenmez.
        """
        if self.APP_ENV == "production":
            if self.SECRET_KEY == "change-this-to-a-random-secret-key-in-production":  # noqa: S105
                raise ValueError("Production'da SECRET_KEY değiştirilmeli!")
            if self.APP_DEBUG:
                raise ValueError("Production'da DEBUG kapalı olmalı!")
            frontend_url = (self.FRONTEND_URL or "").strip().lower()
            if not frontend_url:
                raise ValueError("Production'da FRONTEND_URL ayarlanmalı!")
            if "localhost" in frontend_url or "127.0.0.1" in frontend_url:
                raise ValueError("Production'da FRONTEND_URL gerçek frontend domain'i olmalı!")
            insecure_passwords = {"changeme", "admin", "password", "123456", ""}
            if (self.ADMIN_PASSWORD or "").strip().lower() in insecure_passwords:
                raise ValueError("Production'da ADMIN_PASSWORD güvenli bir değere ayarlanmalı!")
            self.RATE_LIMIT_ENABLED = True
            if not self.JWT_PRIVATE_KEY_PATH.exists():
                raise ValueError(
                    f"JWT private key bulunamadı: {self.JWT_PRIVATE_KEY_PATH}. "
                    "'make generate-keys' komutu ile oluşturun."
                )
            if not self.JWT_PUBLIC_KEY_PATH.exists():
                raise ValueError(
                    f"JWT public key bulunamadı: {self.JWT_PUBLIC_KEY_PATH}. "
                    "'make generate-keys' komutu ile oluşturun."
                )
        return self

    @property
    def is_production(self) -> bool:
        """Uygulamanın production ortamında çalışıp çalışmadığını kontrol eder.

        Returns:
            APP_ENV="production" ise True, değilse False

        Example:
            >>> settings.APP_ENV = "production"
            >>> settings.is_production
            True
        """
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        """Uygulamanın development ortamında çalışıp çalışmadığını kontrol eder.

        Returns:
            APP_ENV="development" ise True, değilse False

        Example:
            >>> settings.APP_ENV = "development"
            >>> settings.is_development
            True
        """
        return self.APP_ENV == "development"


@lru_cache
def get_settings() -> Settings:
    """Singleton settings instance döner.

    @lru_cache ile cache'lenir, böylece uygulama boyunca tek bir
    Settings instance kullanılır. Her çağrıda .env dosyası tekrar
    okunmaz, ilk oluşturulan instance döner.

    Returns:
        Singleton Settings instance

    Note:
        Tüm uygulama bu fonksiyonu kullanmalıdır.
        Direkt Settings() yerine get_settings() çağrılmalı.

    Example:
        >>> from app.core.config import get_settings
        >>> settings = get_settings()
        >>> settings.APP_NAME
        'FastAPI App'
    """
    return Settings()


settings = get_settings()
