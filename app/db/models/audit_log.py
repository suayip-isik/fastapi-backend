"""
Audit log modeli — kim, ne zaman, ne yaptı.
"""

from __future__ import annotations

from enum import Enum as PyEnum
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import BaseModel


class AuditAction(str, PyEnum):
    """Audit log action tanımları.

    Sistemde loglanacak kullanıcı aksiyonlarını ve sistem olaylarını tanımlar.
    Her aksiyon güvenlik monitoring ve compliance için loglanır.

    Attributes:
        LOGIN_SUCCESS: Başarılı kullanıcı girişi
        LOGIN_FAILED: Başarısız giriş denemesi
        LOGOUT: Kullanıcı çıkışı
        REGISTER: Yeni kullanıcı kaydı
        EMAIL_VERIFIED: Email doğrulama tamamlandı
        PASSWORD_RESET_REQUESTED: Şifre sıfırlama talebi
        PASSWORD_RESET: Şifre sıfırlama tamamlandı
        ADMIN_PASSWORD_RESET_REQUESTED: Admin şifre sıfırlama talebi
        ADMIN_PASSWORD_RESET: Admin şifre sıfırlama tamamlandı
        TOKEN_REFRESHED: Access token yenilendi
        PROFILE_UPDATED: Kullanıcı profili güncellendi
        USER_DEACTIVATED: Kullanıcı hesabı deaktif edildi
        USER_ACTIVATED: Kullanıcı hesabı aktif edildi
        ROLE_CHANGED: Kullanıcı rolü değiştirildi
        ADMIN_USER_CREATED: Yeni admin kullanıcı oluşturuldu
        ADMIN_INVITE_RESENT: Admin kullanıcı daveti yeniden gönderildi
        USER_DELETED: Kullanıcı hesabı silindi (soft delete)
        USER_RESTORED: Silinen kullanıcı geri yüklendi
        FILE_UPLOADED: Dosya yüklendi
        FILE_DELETED: Dosya silindi
        API_KEY_CREATED: API key oluşturuldu
        API_KEY_REVOKED: API key iptal edildi
        API_KEY_USED: API key ile kimlik doğrulaması yapıldı
        TOTP_SETUP_STARTED: TOTP 2FA kurulumu başlatıldı
        TOTP_ENABLED: TOTP 2FA aktif edildi
        TOTP_DISABLED: TOTP 2FA devre dışı bırakıldı
        TOTP_BACKUP_CODES_REGENERATED: TOTP backup kodları yenilendi
        ROLE_CREATED: Yeni rol oluşturuldu
        ROLE_UPDATED: Rol güncellendi
        ROLE_DELETED: Rol silindi
        NOTIFICATION_READ: Bildirim okundu olarak işaretlendi
        NOTIFICATION_DELETED: Bildirim silindi
    """

    # Auth
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    REGISTER = "register"
    EMAIL_VERIFIED = "email_verified"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    PASSWORD_RESET = "password_reset"
    ADMIN_PASSWORD_RESET_REQUESTED = "admin_password_reset_requested"
    ADMIN_PASSWORD_RESET = "admin_password_reset"
    TOKEN_REFRESHED = "token_refreshed"
    # User
    PROFILE_UPDATED = "profile_updated"
    USER_DEACTIVATED = "user_deactivated"
    USER_ACTIVATED = "user_activated"
    ROLE_CHANGED = "role_changed"
    ADMIN_USER_CREATED = "admin_user_created"
    ADMIN_INVITE_RESENT = "admin_invite_resent"
    USER_DELETED = "user_deleted"
    USER_RESTORED = "user_restored"
    # Account
    PASSWORD_CHANGED = "password_changed"
    ACCOUNT_DELETED = "account_deleted"
    # File
    FILE_UPLOADED = "file_uploaded"
    FILE_DELETED = "file_deleted"
    # API Key
    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"
    API_KEY_USED = "api_key_used"
    # TOTP / 2FA
    TOTP_SETUP_STARTED = "totp_setup_started"
    TOTP_ENABLED = "totp_enabled"
    TOTP_DISABLED = "totp_disabled"
    TOTP_BACKUP_CODES_REGENERATED = "totp_backup_codes_regenerated"
    # Role management
    ROLE_CREATED = "role_created"
    ROLE_UPDATED = "role_updated"
    ROLE_DELETED = "role_deleted"
    # Notification
    NOTIFICATION_READ = "notification_read"
    NOTIFICATION_DELETED = "notification_deleted"


class AuditLog(BaseModel):
    """Audit log modeli.

    Kullanıcı aksiyonlarını ve sistem olaylarını loglar. Güvenlik
    monitoring, compliance ve forensic analiz için kullanılır.
    Tüm kritik işlemler otomatik olarak loglanır.

    Attributes:
        user_id: Aksiyonu yapan kullanıcı ID'si (nullable, sistem olayları için None olabilir)
        action: Yapılan aksiyon tipi (AuditAction enum)
        ip_address: İstek yapan IP adresi (IPv4/IPv6 destekler, max 45 karakter)
        user_agent: Client user agent string (tarayıcı/uygulama bilgisi)
        extra: Ek JSON detaylar (aksiyon bazlı farklı bilgiler içerebilir)

    Note:
        - Loglar immutable'dır (update/delete yapılmaz)
        - user_id SET NULL ile kullanıcı silinse de log kalır
        - action ve user_id indexlidir (hızlı filtreleme için)
        - ip_address IPv6 için 45 karakter (8 group * 4 hex + 7 colon)
        - extra JSONB ile flexible data storage
        - BaseModel'den created_at, updated_at, id inherit eder

    Example:
        >>> log = AuditLog(
        ...     user_id=user.id,
        ...     action=AuditAction.LOGIN_SUCCESS,
        ...     ip_address="192.168.1.100",
        ...     user_agent="Mozilla/5.0 ...",
        ...     extra={"method": "email_password", "mfa_used": False}
        ... )
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_user_created", "user_id", "created_at"),
        Index("ix_audit_action_created", "action", "created_at"),
    )

    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="auditaction"),
        nullable=False,
        index=True,
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
