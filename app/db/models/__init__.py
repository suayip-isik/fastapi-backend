"""
ORM modelleri.
Alembic autogenerate için tüm modeller buradan import edilir.
"""

from app.db.models.api_key import APIKey
from app.db.models.audit_log import AuditAction, AuditLog
from app.db.models.base import Base, BaseModel, TimestampMixin, UUIDMixin
from app.db.models.notification import Notification, NotificationType
from app.db.models.oauth_account import OAuthAccount
from app.db.models.totp_backup_code import TOTPBackupCode
from app.db.models.user import User, UserRole

__all__ = [
    "Base",
    "BaseModel",
    "TimestampMixin",
    "UUIDMixin",
    "User",
    "UserRole",
    "OAuthAccount",
    "AuditLog",
    "AuditAction",
    "APIKey",
    "Notification",
    "NotificationType",
    "TOTPBackupCode",
]
