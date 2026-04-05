"""migrate to db-driven rbac

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-04-04 00:00:00.000000

Değişiklikler:
- `roles` tablosu oluşturulur (sistem rolleri seed edilir)
- `role_permissions` tablosu oluşturulur (her rol için permission'lar seed edilir)
- `users.role_id` UUID FK kolonu eklenir
- Mevcut `users.role` enum değerleri `role_id`'ye migrate edilir
- `users.role` eski enum kolonu ve `userrole` tipi kaldırılır
- `ix_users_filters` composite index güncellenir (role yerine role_id)
"""
from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ── Permission sabitleri (app.core.permissions'ı import etmez — migration bağımsız olmalı) ──

_ADMIN_PERMISSIONS = [
    "admin:access",
    "users:read", "users:write", "users:delete",
    "roles:read", "roles:write",
    "audit:read",
    "api_keys:read", "api_keys:write",
    "notifications:read",
    "profile:read", "profile:write",
]

_USER_PERMISSIONS = [
    "profile:read", "profile:write",
    "api_keys:read", "api_keys:write",
    "notifications:read",
]

_MODERATOR_PERMISSIONS = [
    "profile:read", "profile:write",
    "users:read",
    "audit:read",
    "notifications:read",
]

_SYSTEM_ROLES = [
    {"name": "admin",     "description": "Tam yetkili sistem yöneticisi", "permissions": _ADMIN_PERMISSIONS},
    {"name": "user",      "description": "Standart kullanıcı",            "permissions": _USER_PERMISSIONS},
    {"name": "moderator", "description": "İçerik moderatörü",             "permissions": _MODERATOR_PERMISSIONS},
]


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. roles tablosu ─────────────────────────────────────────────────────
    op.create_table(
        "roles",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(50), unique=True, nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_roles_name", "roles", ["name"], unique=True)

    # ── 2. role_permissions tablosu ──────────────────────────────────────────
    op.create_table(
        "role_permissions",
        sa.Column(
            "role_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("permission", sa.String(100), primary_key=True, nullable=False),
    )

    # ── 3. Sistem rollerini ve permission'larını seed et ─────────────────────
    role_ids: dict[str, str] = {}
    for role_data in _SYSTEM_ROLES:
        role_id = str(uuid.uuid4())
        role_ids[role_data["name"]] = role_id
        conn.execute(
            sa.text(
                "INSERT INTO roles (id, name, description, is_system) "
                "VALUES (:id, :name, :description, true)"
            ),
            {"id": role_id, "name": role_data["name"], "description": role_data["description"]},
        )
        for perm in role_data["permissions"]:
            conn.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission) VALUES (:role_id, :permission)"
                ),
                {"role_id": role_id, "permission": perm},
            )

    # ── 4. users.role_id kolonu ekle (nullable — önce doldur sonra kısıtla) ──
    op.add_column(
        "users",
        sa.Column("role_id", PG_UUID(as_uuid=True), nullable=True),
    )

    # ── 5. Mevcut role enum değerlerini role_id'ye migrate et ────────────────
    for role_name, role_id in role_ids.items():
        conn.execute(
            sa.text("UPDATE users SET role_id = :role_id WHERE lower(role::text) = :role_name"),
            {"role_id": role_id, "role_name": role_name},
        )

    # ── 6. role_id NOT NULL + FK constraint ekle ────────────────────────────
    op.alter_column("users", "role_id", nullable=False)
    op.create_foreign_key(
        "fk_users_role_id",
        "users",
        "roles",
        ["role_id"],
        ["id"],
    )
    op.create_index("ix_users_role_id", "users", ["role_id"])

    # ── 7. ix_users_filters composite index güncelle (role → role_id) ────────
    op.drop_index("ix_users_filters", table_name="users")
    op.create_index("ix_users_filters", "users", ["role_id", "is_active", "is_verified", "deleted_at"])

    # ── 8. Eski role kolonu ve userrole enum tipini kaldır ───────────────────
    op.drop_column("users", "role")
    op.execute("DROP TYPE IF EXISTS userrole")


def downgrade() -> None:
    conn = op.get_bind()

    # ── 1. Eski enum tipini ve role kolonunu geri ekle ───────────────────────
    op.execute("CREATE TYPE userrole AS ENUM ('admin', 'user', 'moderator')")
    op.add_column(
        "users",
        sa.Column("role", sa.Enum("admin", "user", "moderator", name="userrole"), nullable=True),
    )

    # ── 2. role_id'den role kolonunu doldur ──────────────────────────────────
    conn.execute(
        sa.text(
            "UPDATE users SET role = r.name::userrole "
            "FROM roles r WHERE users.role_id = r.id"
        )
    )
    op.alter_column("users", "role", nullable=False)

    # ── 3. ix_users_filters index'ini eski haline döndür ─────────────────────
    op.drop_index("ix_users_filters", table_name="users")
    op.create_index("ix_users_filters", "users", ["role", "is_active", "is_verified", "deleted_at"])

    # ── 4. FK ve role_id kolonu kaldır ────────────────────────────────────────
    op.drop_index("ix_users_role_id", table_name="users")
    op.drop_constraint("fk_users_role_id", "users", type_="foreignkey")
    op.drop_column("users", "role_id")

    # ── 5. role_permissions ve roles tablolarını kaldır ───────────────────────
    op.drop_table("role_permissions")
    op.drop_index("ix_roles_name", table_name="roles")
    op.drop_table("roles")
