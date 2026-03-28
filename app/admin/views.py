"""
SQLAdmin view tanımları.
Her model için admin panelinde görünecek alanlar ve işlemler burada tanımlanır.
"""

from __future__ import annotations

from sqladmin import ModelView

from app.db.models.audit_log import AuditLog
from app.db.models.oauth_account import OAuthAccount
from app.db.models.user import User


class UserAdmin(ModelView, model=User):
    name = "Kullanıcı"
    name_plural = "Kullanıcılar"
    icon = "fa-solid fa-users"

    # Listede görünecek kolonlar
    column_list = [
        User.id,
        User.email,
        User.full_name,
        User.role,
        User.is_active,
        User.is_verified,
        User.created_at,
    ]

    # Arama yapılabilecek kolonlar
    column_searchable_list = [User.email, User.full_name, User.username]

    # Filtrelenebilecek kolonlar
    column_filters = [User.role, User.is_active, User.is_verified]

    # Sıralanabilecek kolonlar
    column_sortable_list = [User.email, User.created_at, User.role]

    # Detay sayfasında görünecek kolonlar
    column_details_list = [
        User.id,
        User.email,
        User.username,
        User.full_name,
        User.avatar_url,
        User.role,
        User.is_active,
        User.is_verified,
        User.created_at,
        User.updated_at,
    ]

    # Form'da görünecek alanlar (create/edit)
    form_columns = [
        User.email,
        User.username,
        User.full_name,
        User.role,
        User.is_active,
        User.is_verified,
    ]

    # Gizlenecek hassas alanlar
    # form_excluded_columns = [User.hashed_password]

    # Sayfa başına kayıt sayısı
    page_size = 25
    page_size_options = [25, 50, 100]

    # İzinler
    can_create = True
    can_edit = True
    can_delete = True
    can_view_details = True
    can_export = True


class OAuthAccountAdmin(ModelView, model=OAuthAccount):
    name = "OAuth Hesabı"
    name_plural = "OAuth Hesapları"
    icon = "fa-solid fa-key"

    column_list = [
        OAuthAccount.id,
        OAuthAccount.user_id,
        OAuthAccount.provider,
        OAuthAccount.email,
        OAuthAccount.created_at,
    ]

    column_searchable_list = [OAuthAccount.email, OAuthAccount.provider]
    column_filters = [OAuthAccount.provider]
    column_sortable_list = [OAuthAccount.provider, OAuthAccount.created_at]

    column_details_list = [
        OAuthAccount.id,
        OAuthAccount.user_id,
        OAuthAccount.provider,
        OAuthAccount.provider_user_id,
        OAuthAccount.email,
        OAuthAccount.created_at,
        OAuthAccount.updated_at,
    ]

    # Token'lar form'da görünmesin
    form_excluded_columns = [
        OAuthAccount.access_token,
        OAuthAccount.refresh_token,
    ]

    can_create = False  # OAuth hesapları manuel oluşturulmaz
    can_edit = False  # Token'lar manuel düzenlenmez
    can_delete = True
    can_view_details = True
    can_export = False  # Token bilgileri export edilmesin


class AuditLogAdmin(ModelView, model=AuditLog):
    name = "Audit Log"
    name_plural = "Audit Loglar"
    icon = "fa-solid fa-shield-halved"

    column_list = [
        AuditLog.created_at,
        AuditLog.action,
        AuditLog.user_id,
        AuditLog.ip_address,
        AuditLog.user_agent,
    ]

    column_searchable_list = [AuditLog.ip_address]
    column_filters = [AuditLog.action, AuditLog.user_id]
    column_sortable_list = [AuditLog.created_at, AuditLog.action]

    column_details_list = [
        AuditLog.id,
        AuditLog.created_at,
        AuditLog.action,
        AuditLog.user_id,
        AuditLog.ip_address,
        AuditLog.user_agent,
        AuditLog.extra,
    ]

    page_size = 50
    page_size_options = [50, 100, 200]

    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True
    can_export = True
