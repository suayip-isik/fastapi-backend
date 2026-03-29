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
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Alembic için sync URL."""
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
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ── JWT / Auth ────────────────────────────────────────────────────────────
    JWT_PRIVATE_KEY_PATH: Path = Path("./keys/private.pem")
    JWT_PUBLIC_KEY_PATH: Path = Path("./keys/public.pem")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    @property
    def JWT_PRIVATE_KEY(self) -> str:
        return self.JWT_PRIVATE_KEY_PATH.read_text()

    @property
    def JWT_PUBLIC_KEY(self) -> str:
        return self.JWT_PUBLIC_KEY_PATH.read_text()

    # ── OAuth2 ────────────────────────────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""

    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_REDIRECT_URI: str = ""

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
    RATE_LIMIT_AUTH: str = "5/minute"  # login, reset-password
    RATE_LIMIT_AUTH_EMAIL: str = "3/hour"  # forgot-password, resend-verification
    RATE_LIMIT_REGISTER: str = "3/hour"  # register
    RATE_LIMIT_UPLOAD: str = "20/hour"

    # ── Sentry ────────────────────────────────────────────────────────────────
    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1  # production için 0.1, dev için 1.0

    @field_validator("SENTRY_DSN", mode="before")
    @classmethod
    def _strip_sentry_dsn(cls, v: object) -> str:
        """Inline comment ve boşlukları temizle; geçersiz DSN'i boş stringe çevir."""
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
        if isinstance(v, str):
            result: list[Any] = json.loads(v)
            return result
        return list(v)

    @field_validator("ALLOWED_UPLOAD_TYPES", mode="before")
    @classmethod
    def parse_upload_types(cls, v: Any) -> list[Any]:
        if isinstance(v, str):
            result: list[Any] = json.loads(v)
            return result
        return list(v)

    @model_validator(mode="after")
    def validate_production_settings(self) -> Settings:
        if self.APP_ENV == "production":
            if self.SECRET_KEY == "change-this-to-a-random-secret-key-in-production":  # noqa: S105
                raise ValueError("Production'da SECRET_KEY değiştirilmeli!")
            if self.APP_DEBUG:
                raise ValueError("Production'da DEBUG kapalı olmalı!")
            insecure_passwords = {"changeme", "admin", "password", "123456", ""}
            if (self.ADMIN_PASSWORD or "").strip().lower() in insecure_passwords:
                raise ValueError("Production'da ADMIN_PASSWORD güvenli bir değere ayarlanmalı!")
        return self

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"


@lru_cache
def get_settings() -> Settings:
    """Singleton settings instance — her yerde bu fonksiyon kullanılır."""
    return Settings()


settings = get_settings()
