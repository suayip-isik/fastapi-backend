"""Config settings unit testleri."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings


def _write_keypair(tmp_path: Path) -> tuple[Path, Path]:
    private_key = tmp_path / "private.pem"
    public_key = tmp_path / "public.pem"
    private_key.write_text("test-private-key")
    public_key.write_text("test-public-key")
    return private_key, public_key


def _base_settings_kwargs(tmp_path: Path) -> dict[str, object]:
    private_key, public_key = _write_keypair(tmp_path)
    return {
        "APP_NAME": "Test App",
        "APP_ENV": "production",
        "APP_DEBUG": False,
        "APP_VERSION": "1.0.0",
        "APP_URL": "https://api.example.com",
        "FRONTEND_URL": "https://app.example.com",
        "SECRET_KEY": "super-secret-key-that-is-long-enough-32chars",
        "ALLOWED_HOSTS": ["api.example.com"],
        "CORS_ORIGINS": ["https://app.example.com"],
        "POSTGRES_HOST": "db",
        "POSTGRES_PORT": 5432,
        "POSTGRES_DB": "appdb",
        "POSTGRES_USER": "appuser",
        "POSTGRES_PASSWORD": "strongpassword",
        "REDIS_HOST": "redis",
        "REDIS_PORT": 6379,
        "REDIS_PASSWORD": "strongredispassword",
        "REDIS_DB": 0,
        "JWT_PRIVATE_KEY_PATH": private_key,
        "JWT_PUBLIC_KEY_PATH": public_key,
        "SUPERADMIN_USERNAME": "superadmin",
        "SUPERADMIN_EMAIL": "superadmin@example.com",
        "SUPERADMIN_PASSWORD": "StrongAdminPass1",
        "DEFAULT_APP_USER_USERNAME": "suayip",
        "DEFAULT_APP_USER_EMAIL": "suayip@example.com",
        "DEFAULT_APP_USER_PASSWORD": "StrongAppPass1",
        "RATE_LIMIT_ENABLED": False,
    }


def test_production_settings_force_rate_limits_enabled(tmp_path: Path) -> None:
    """Production'da rate limiting kapatılamaz."""
    settings = Settings(**_base_settings_kwargs(tmp_path))
    assert settings.RATE_LIMIT_ENABLED is True


def test_production_settings_require_non_local_frontend_url(tmp_path: Path) -> None:
    """Production'da localhost FRONTEND_URL reddedilmeli."""
    kwargs = _base_settings_kwargs(tmp_path)
    kwargs["FRONTEND_URL"] = "http://localhost:3000"

    with pytest.raises(ValueError, match="FRONTEND_URL"):
        Settings(**kwargs)
