"""
Admin kullanıcı oluşturma / rol atama scripti.

Kullanım:
    # Mevcut kullanıcıyı admin yap
    docker compose exec api python scripts/make_admin.py --email user@example.com

    # Yeni admin kullanıcı oluştur
    docker compose exec api python scripts/make_admin.py --email admin@example.com --password Admin1234 --create
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import text

sys.path.insert(0, "/app")

from app.core.config import settings
from app.core.security import hash_password


async def make_admin(email: str) -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    async with AsyncSession(engine) as session:
        result = await session.execute(
            text("SELECT id, email, role FROM users WHERE email = :email"),
            {"email": email},
        )
        user = result.fetchone()

        if not user:
            print(f"❌ Kullanıcı bulunamadı: {email}")
            await engine.dispose()
            sys.exit(1)

        if user.role == "ADMIN":
            print(f"ℹ️  {email} zaten admin.")
            await engine.dispose()
            return

        await session.execute(
            text("UPDATE users SET role = 'ADMIN'::userrole WHERE email = :email"),
            {"email": email},
        )
        await session.commit()
        print(f"✅ {email} admin yapıldı.")

    await engine.dispose()


async def create_admin(email: str, password: str) -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    async with AsyncSession(engine) as session:
        result = await session.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": email},
        )
        existing = result.fetchone()

        if existing:
            print(f"⚠️  {email} zaten mevcut. Rolü admin yapılıyor...")
            await session.execute(
                text("UPDATE users SET role = 'ADMIN'::userrole WHERE email = :email"),
                {"email": email},
            )
            await session.commit()
            print(f"✅ {email} admin yapıldı.")
        else:
            hashed = hash_password(password)
            await session.execute(
                text("""
                    INSERT INTO users (email, hashed_password, role, is_active, is_verified)
                    VALUES (:email, :password, 'ADMIN'::userrole, true, true)
                """),
                {"email": email, "password": hashed},
            )
            await session.commit()
            print(f"✅ Admin kullanıcı oluşturuldu: {email}")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Admin kullanıcı yönetimi")
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
