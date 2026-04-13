"""Mevcut kullanıcıyı panel_admin yap veya yeni panel_admin oluştur."""

from __future__ import annotations

import argparse
import asyncio
import sys
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

sys.path.insert(0, "/app")

from app.core.config import settings
from app.core.security import hash_password
from app.core.system_roles import PANEL_ADMIN_ROLE


async def make_admin(email: str) -> None:
    """Mevcut kullanıcının rolünü panel_admin olarak günceller."""
    engine = create_async_engine(settings.DATABASE_URL)
    async with AsyncSession(engine) as session:
        result = await session.execute(
            text(
                """
                SELECT users.id, roles.name AS role_name
                FROM users
                JOIN roles ON roles.id = users.role_id
                WHERE users.email = :email
                """
            ),
            {"email": email},
        )
        user = result.fetchone()

        if not user:
            print(f"❌ Kullanıcı bulunamadı: {email}")
            await engine.dispose()
            sys.exit(1)

        if user.role_name == PANEL_ADMIN_ROLE:
            print(f"ℹ️  {email} zaten {PANEL_ADMIN_ROLE}.")
            await engine.dispose()
            return

        await session.execute(
            text(
                """
                UPDATE users
                SET role_id = (SELECT id FROM roles WHERE name = :role_name AND deleted_at IS NULL),
                    surface = 'admin'
                WHERE email = :email
                """
            ),
            {"email": email, "role_name": PANEL_ADMIN_ROLE},
        )
        await session.commit()
        print(f"✅ {email} {PANEL_ADMIN_ROLE} yapıldı.")

    await engine.dispose()


async def create_admin(email: str, password: str) -> None:
    """Yeni panel_admin kullanıcı oluşturur veya mevcutsa rolünü günceller."""
    engine = create_async_engine(settings.DATABASE_URL)
    async with AsyncSession(engine) as session:
        result = await session.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": email},
        )
        existing = result.fetchone()

        if existing:
            print(f"⚠️  {email} zaten mevcut. Rolü {PANEL_ADMIN_ROLE} yapılıyor...")
            await session.execute(
                text(
                    """
                    UPDATE users
                    SET role_id = (SELECT id FROM roles WHERE name = :role_name AND deleted_at IS NULL),
                        surface = 'admin'
                    WHERE email = :email
                    """
                ),
                {"email": email, "role_name": PANEL_ADMIN_ROLE},
            )
            await session.commit()
            print(f"✅ {email} {PANEL_ADMIN_ROLE} yapıldı.")
        else:
            hashed = hash_password(password)
            await session.execute(
                text("""
                    INSERT INTO users (
                        email,
                        username,
                        hashed_password,
                        surface,
                        role_id,
                        is_active,
                        is_verified,
                        id
                    )
                    VALUES (
                        :email,
                        :username,
                        :password,
                        'admin',
                        (SELECT id FROM roles WHERE name = :role_name AND deleted_at IS NULL),
                        true,
                        true,
                        :id
                    )
                """),
                {
                    "email": email,
                    "username": email.split("@", 1)[0],
                    "id": uuid4(),
                    "password": hashed,
                    "role_name": PANEL_ADMIN_ROLE,
                },
            )
            await session.commit()
            print(f"✅ {PANEL_ADMIN_ROLE} kullanıcı oluşturuldu: {email}")

    await engine.dispose()


def main() -> None:
    """CLI argümanlarını parse eder ve ilgili admin işlemini çalıştırır."""
    parser = argparse.ArgumentParser(description="Panel admin kullanıcı yönetimi")
    parser.add_argument("--email", required=True, help="Kullanıcı e-posta adresi")
    parser.add_argument("--password", default="Admin1234!", help="Şifre (--create ile kullanılır)")
    parser.add_argument("--create", action="store_true", help="Kullanıcı yoksa oluştur")
    args = parser.parse_args()

    if args.create:
        asyncio.run(create_admin(args.email, args.password))
    else:
        asyncio.run(make_admin(args.email))


if __name__ == "__main__":
    main()
