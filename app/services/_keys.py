"""
Redis key sabitleri — service katmanında kullanılır.
Format: KEY.format(token_or_jti)
"""

EMAIL_VERIFY_KEY = "email_verify:{}"
PASSWORD_RESET_KEY = "password_reset:{}"
BLACKLIST_KEY = "blacklist:{}"
TOTP_BACKUP_KEY = "totp_backup:{}"  # {user_id} → set of backup codes
OAUTH_STATE_KEY = "oauth_state:{}"  # {state} → "1", TTL=600s

# Cache
USER_CACHE_KEY = "user_cache:id:{}"  # {user_id} → UserResponse JSON
USER_EMAIL_CACHE_KEY = "user_cache:email:{}"  # {email} → UserResponse JSON
USER_CACHE_TTL = 5 * 60  # 300 saniye
