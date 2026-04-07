"""add_audit_actions_api_key_totp_constraints

Revision ID: 1b9a3da075fa
Revises: c6d7e8f9a0b1
Create Date: 2026-04-07 22:18:38.606104

Değişiklikler:
- AuditAction enum'a yeni action'lar eklendi (API key, TOTP, rol yönetimi)
- api_keys: (user_id, key_prefix) unique constraint eklendi
- totp_backup_codes: (user_id, code_hash) unique constraint + index eklendi
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = '1b9a3da075fa'
down_revision: Union[str, None] = 'c6d7e8f9a0b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Eklenecek yeni AuditAction enum değerleri
NEW_AUDIT_ACTIONS = [
    "api_key_created",
    "api_key_revoked",
    "api_key_used",
    "totp_setup_started",
    "totp_enabled",
    "totp_disabled",
    "totp_backup_codes_regenerated",
    "role_created",
    "role_updated",
    "role_deleted",
]


def upgrade() -> None:
    # AuditAction enum'a yeni değerler ekle
    for action in NEW_AUDIT_ACTIONS:
        op.execute(f"ALTER TYPE auditaction ADD VALUE IF NOT EXISTS '{action}'")

    # api_keys: (user_id, key_prefix) unique constraint
    op.create_unique_constraint('uq_api_key_user_prefix', 'api_keys', ['user_id', 'key_prefix'])

    # totp_backup_codes: (user_id, code_hash) index + unique constraint
    op.create_index('ix_totp_backup_code_hash', 'totp_backup_codes', ['user_id', 'code_hash'], unique=False)
    op.create_unique_constraint('uq_totp_backup_user_hash', 'totp_backup_codes', ['user_id', 'code_hash'])


def downgrade() -> None:
    # Unique constraint'leri ve index'i geri al
    # Not: PostgreSQL enum değerleri downgrade'de kaldırılamaz (ALTER TYPE DROP VALUE yok)
    op.drop_constraint('uq_totp_backup_user_hash', 'totp_backup_codes', type_='unique')
    op.drop_index('ix_totp_backup_code_hash', table_name='totp_backup_codes')
    op.drop_constraint('uq_api_key_user_prefix', 'api_keys', type_='unique')
