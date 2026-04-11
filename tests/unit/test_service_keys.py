"""Email verification key helper testleri."""

from __future__ import annotations

from app.services._keys import decode_email_verify_value, encode_email_verify_value


def test_encode_email_verify_value_without_target_email_returns_user_id() -> None:
    """Legacy davranışta yalnız user_id döndürülmeli."""
    assert encode_email_verify_value("user-123") == "user-123"


def test_encode_email_verify_value_lowercases_target_email() -> None:
    """Yeni format target email'i lowercase saklamalı."""
    assert (
        encode_email_verify_value("user-123", "User@Example.com")
        == "user-123|user@example.com"
    )


def test_decode_email_verify_value_supports_legacy_format() -> None:
    """Separator olmayan legacy format desteklenmeli."""
    assert decode_email_verify_value("user-legacy") == ("user-legacy", None)


def test_decode_email_verify_value_supports_target_email_format() -> None:
    """Yeni formatta email lower-case olarak çözülmeli."""
    assert decode_email_verify_value("user-123|User@Example.com") == (
        "user-123",
        "user@example.com",
    )
