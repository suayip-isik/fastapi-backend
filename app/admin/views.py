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
    """User modeli için SQLAdmin panel view.

    Kullanıcıları listeleme, görüntüleme, düzenleme ve silme işlemlerini
    sağlar. Hassas alanlar (şifre hash, TOTP secret) formda gizlidir.

    Attributes:
        column_list: Listede gösterilen kolonlar (id, email, full_name, role, vb.)
        column_searchable_list: Arama yapılabilen alanlar (email, full_name, username)
        column_filters: Filtreleme için kullanılabilecek alanlar (role, is_active, is_verified)
        column_details_list: Detay sayfasında görünen tüm kolonlar
        form_columns: Create/edit formunda düzenlenebilecek alanlar
        form_excluded_columns: Formda görünmeyecek hassas alanlar
        page_size: Sayfa başına gösterilen kayıt sayısı (25)

    Note:
        - hashed_password ve totp_secret formda görünmez
        - Tüm CRUD operasyonları aktif (create, edit, delete, view, export)
    """

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
    """OAuthAccount modeli için SQLAdmin panel view.

    OAuth hesaplarını (Google, GitHub) görüntüleme ve silme işlemlerini
    sağlar. Güvenlik nedeniyle manuel oluşturma ve düzenleme kapalıdır.

    Attributes:
        column_list: Listede gösterilen kolonlar (id, user_id, provider, email, created_at)
        column_searchable_list: Arama yapılabilen alanlar (email, provider)
        column_filters: Filtreleme için kullanılabilecek alanlar (provider)
        column_details_list: Detay sayfasında görünen kolonlar
        form_excluded_columns: Formda görünmeyecek hassas alanlar (access_token, refresh_token)

    Note:
        - OAuth hesapları manuel oluşturulamaz (can_create=False)
        - Token bilgileri düzenlenemez (can_edit=False)
        - Güvenlik nedeniyle export yapılamaz (can_export=False)
        - Sadece görüntüleme ve silme aktif
    """

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
    """AuditLog modeli için SQLAdmin panel view.

    Sistem denetim kayıtlarını (audit logs) görüntüleme ve dışa aktarma
    işlemlerini sağlar. Salt okunur - kayıtlar değiştirilemez veya silinemez.

    Attributes:
        column_list: Listede gösterilen kolonlar (created_at, action, user_id, ip_address, user_agent)
        column_searchable_list: Arama yapılabilen alanlar (ip_address)
        column_filters: Filtreleme için kullanılabilecek alanlar (action, user_id)
        column_details_list: Detay sayfasında görünen tüm kolonlar (extra JSON dahil)
        page_size: Sayfa başına gösterilen kayıt sayısı (50)

    Note:
        - Salt okunur view (can_create, can_edit, can_delete=False)
        - Sadece görüntüleme ve export aktif
        - Denetim kaydı bütünlüğü korunur
    """

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
