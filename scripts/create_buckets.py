"""
MinIO / S3 bucket kurulum scripti.
Uygulama için gerekli bucket'ları oluşturur.

Kullanım:
    docker compose exec api python scripts/create_buckets.py
"""

from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, "/app")

import aioboto3
from botocore.exceptions import ClientError

from app.core.config import settings


async def create_bucket(s3_client, bucket_name: str) -> None:
    try:
        await s3_client.head_bucket(Bucket=bucket_name)
        print(f"ℹ️  Bucket zaten mevcut: {bucket_name}")
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "404":
            await s3_client.create_bucket(Bucket=bucket_name)
            print(f"✅ Bucket oluşturuldu: {bucket_name}")
        else:
            print(f"❌ Hata ({bucket_name}): {e}")
            raise


async def setup_buckets() -> None:
    print(f"🔌 MinIO bağlantısı kuruluyor: {settings.S3_ENDPOINT_URL}")

    session = aioboto3.Session(
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
    )

    async with session.client("s3", endpoint_url=settings.S3_ENDPOINT_URL) as s3:
        # Ana uygulama bucket'ı
        await create_bucket(s3, settings.S3_BUCKET_NAME)

        # Ek bucket'lar buraya eklenebilir
        # await create_bucket(s3, "app-backups")
        # await create_bucket(s3, "app-temp")

    print("\n✅ Bucket kurulumu tamamlandı.")


if __name__ == "__main__":
    asyncio.run(setup_buckets())
