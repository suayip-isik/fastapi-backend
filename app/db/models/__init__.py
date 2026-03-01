"""
ORM modelleri.
Alembic autogenerate için tüm modeller buradan import edilir.
"""
from app.db.models.base import Base, BaseModel, TimestampMixin, UUIDMixin
from app.db.models.user import User, UserRole
from app.db.models.oauth_account import OAuthAccount

__all__ = [
    "Base",
    "BaseModel",
    "TimestampMixin",
    "UUIDMixin",
    "User",
    "UserRole",
    "OAuthAccount",
]
