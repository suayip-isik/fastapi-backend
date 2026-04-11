"""User avatar helper testleri."""

from uuid import uuid4

from app.services.user import _extract_managed_storage_key


def test_extract_managed_storage_key_accepts_direct_key() -> None:
    user_id = uuid4()
    key = f"users/{user_id}/avatars/avatar.jpg"

    assert _extract_managed_storage_key(key, user_id=user_id) == key


def test_extract_managed_storage_key_parses_bucket_path_url() -> None:
    user_id = uuid4()
    key = f"users/{user_id}/avatars/avatar.jpg"
    url = f"http://minio:9000/app-uploads/{key}?X-Amz-Signature=test"

    assert _extract_managed_storage_key(url, user_id=user_id) == key


def test_extract_managed_storage_key_rejects_foreign_url() -> None:
    user_id = uuid4()

    assert (
        _extract_managed_storage_key("https://cdn.example.com/avatar.png", user_id=user_id) is None
    )
