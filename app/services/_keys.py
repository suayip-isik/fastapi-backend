"""
Redis key sabitleri — service katmanında kullanılır.
Format: KEY.format(token_or_jti)
"""

from __future__ import annotations

from typing import Final

from app.core.config import settings

EMAIL_VERIFY_KEY = "email_verify:{}"
PASSWORD_RESET_KEY = "password_reset:{}"
LOGIN_PARTIAL_KEY = "login_partial:{}"  # {token} → user_id str, TTL=LOGIN_PARTIAL_TTL
BLACKLIST_KEY = "blacklist:{}"
TOTP_BACKUP_KEY = "totp_backup:{}"  # {user_id} → set of backup codes

# Cache
USER_CACHE_KEY = "user_cache:id:{}"  # {user_id} → UserResponse JSON
USER_EMAIL_CACHE_KEY = "user_cache:email:{}"  # {email} → UserResponse JSON
USER_CACHE_TTL = settings.USER_CACHE_TTL_SECONDS

USER_PERMISSIONS_KEY = "user_permissions:{}"  # {user_id} → permission string listesi JSON
USER_PERMISSIONS_TTL = settings.USER_PERMISSIONS_TTL_SECONDS

_EMAIL_VERIFY_SEPARATOR: Final[str] = "|"


def encode_email_verify_value(user_id: str, target_email: str | None = None) -> str:
    """Email verify Redis value'sunu üretir."""
    if target_email is None:
        return user_id
    return f"{user_id}{_EMAIL_VERIFY_SEPARATOR}{target_email.lower()}"


def decode_email_verify_value(raw_value: str) -> tuple[str, str | None]:
    """Email verify Redis value'sunu çözer.

    Geriye dönük uyumluluk için eski format sadece user_id içerebilir.
    """
    if _EMAIL_VERIFY_SEPARATOR not in raw_value:
        return raw_value, None
    user_id, target_email = raw_value.split(_EMAIL_VERIFY_SEPARATOR, 1)
    return user_id, target_email.lower()
