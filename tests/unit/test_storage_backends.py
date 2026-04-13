"""Storage backend URL üretimi için unit testler."""

from __future__ import annotations

from typing import Any

import pytest

from app.core.config import settings
from app.core.exceptions import StorageError
from app.core.i18n import language_var
from app.storage.backends import S3StorageBackend, _build_public_object_url


class _FakeS3Client:
    def __init__(self, url: str) -> None:
        self._url = url

    async def generate_presigned_url(self, *_args: Any, **_kwargs: Any) -> str:
        return self._url


class _FakeClientContext:
    def __init__(self, url: str) -> None:
        self._url = url

    async def __aenter__(self) -> _FakeS3Client:
        return _FakeS3Client(self._url)

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False


class _FakeSession:
    def __init__(self, url: str) -> None:
        self._url = url

    def client(self, *_args: Any, **_kwargs: Any) -> _FakeClientContext:
        return _FakeClientContext(self._url)


def test_build_public_object_url_uses_public_base(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "S3_PUBLIC_URL", "http://localhost:9000")
    monkeypatch.setattr(settings, "S3_ENDPOINT_URL", "http://minio:9000")
    monkeypatch.setattr(settings, "S3_BUCKET_NAME", "app-uploads")

    assert _build_public_object_url("app-uploads", "users/1/avatar.jpg") == (
        "http://localhost:9000/app-uploads/users/1/avatar.jpg"
    )


def test_build_public_object_url_falls_back_to_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "S3_PUBLIC_URL", "")
    monkeypatch.setattr(settings, "S3_ENDPOINT_URL", "http://minio:9000")
    monkeypatch.setattr(settings, "S3_BUCKET_NAME", "app-uploads")

    assert _build_public_object_url("app-uploads", "users/1/avatar.jpg") == (
        "http://minio:9000/app-uploads/users/1/avatar.jpg"
    )


@pytest.mark.asyncio
async def test_s3_storage_backend_get_url_returns_presigned_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "S3_PUBLIC_URL", "http://localhost:9000")
    monkeypatch.setattr(settings, "S3_BUCKET_NAME", "app-uploads")
    backend = S3StorageBackend()
    backend._session = _FakeSession(
        "http://minio:9000/app-uploads/users/1/avatar.jpg?X-Amz-Signature=test"
    )

    url = await backend.get_url("users/1/avatar.jpg")

    assert url == "http://minio:9000/app-uploads/users/1/avatar.jpg?X-Amz-Signature=test"


@pytest.mark.asyncio
async def test_s3_storage_backend_get_public_url_uses_public_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "S3_PUBLIC_URL", "http://localhost:9000")
    monkeypatch.setattr(settings, "S3_BUCKET_NAME", "app-uploads")
    backend = S3StorageBackend()

    url = await backend.get_public_url("users/1/avatar.jpg")

    assert url == "http://localhost:9000/app-uploads/users/1/avatar.jpg"


@pytest.mark.asyncio
async def test_s3_storage_backend_get_public_url_raises_i18n_error_when_base_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "S3_PUBLIC_URL", "")
    monkeypatch.setattr(settings, "S3_ENDPOINT_URL", "")
    monkeypatch.setattr(settings, "S3_BUCKET_NAME", "app-uploads")
    backend = S3StorageBackend()
    token = language_var.set("tr")

    try:
        with pytest.raises(
            StorageError,
            match="URL üretimi başarısız: Public storage URL tabanı yapılandırılmamış.",
        ):
            await backend.get_public_url("users/1/avatar.jpg")
    finally:
        language_var.reset(token)
