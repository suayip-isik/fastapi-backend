"""
Redis key sabitleri — service katmanında kullanılır.
Format: KEY.format(token_or_jti)
"""

EMAIL_VERIFY_KEY = "email_verify:{}"
PASSWORD_RESET_KEY = "password_reset:{}"
BLACKLIST_KEY = "blacklist:{}"
