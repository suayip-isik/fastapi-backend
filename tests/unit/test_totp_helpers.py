"""TOTP ve API Key yardımcı fonksiyonları için unit testler."""

from __future__ import annotations

import re

import pytest

from app.core.exceptions import AuthenticationError
from app.core.security import decrypt_secret, encrypt_secret
from app.services.api_key import _generate_raw_key, _split_key
from app.services.totp import _generate_backup_codes

# ── encrypt_secret / decrypt_secret ──────────────────────────────────────────


def test_encrypt_decrypt_roundtrip() -> None:
    """test_encrypt_decrypt_roundtrip senaryosunu test eder."""
    plaintext = "my-secret-totp-key"
    ciphertext = encrypt_secret(plaintext)
    assert decrypt_secret(ciphertext) == plaintext


def test_encrypt_produces_different_ciphertext_each_call() -> None:
    """Fernet her şifrelemede rastgele IV kullanır."""
    c1 = encrypt_secret("same-value")
    c2 = encrypt_secret("same-value")
    assert c1 != c2


def test_encrypt_returns_str() -> None:
    """test_encrypt_returns_str senaryosunu test eder."""
    result = encrypt_secret("hello")
    assert isinstance(result, str)


def test_decrypt_returns_str() -> None:
    """test_decrypt_returns_str senaryosunu test eder."""
    ciphertext = encrypt_secret("hello")
    result = decrypt_secret(ciphertext)
    assert isinstance(result, str)


def test_decrypt_wrong_ciphertext_raises_authentication_error() -> None:
    """test_decrypt_wrong_ciphertext_raises_authentication_error senaryosunu test eder."""
    with pytest.raises(AuthenticationError):
        decrypt_secret("not-valid-fernet-ciphertext")


def test_decrypt_empty_string_raises_authentication_error() -> None:
    """test_decrypt_empty_string_raises_authentication_error senaryosunu test eder."""
    with pytest.raises(AuthenticationError):
        decrypt_secret("")


def test_decrypt_tampered_ciphertext_raises_authentication_error() -> None:
    """test_decrypt_tampered_ciphertext_raises_authentication_error senaryosunu test eder."""
    ciphertext = encrypt_secret("secret")
    tampered = ciphertext[:-5] + "XXXXX"
    with pytest.raises(AuthenticationError):
        decrypt_secret(tampered)


def test_encrypt_long_plaintext_roundtrip() -> None:
    """test_encrypt_long_plaintext_roundtrip senaryosunu test eder."""
    long_text = "A" * 1000
    assert decrypt_secret(encrypt_secret(long_text)) == long_text


def test_encrypt_unicode_plaintext_roundtrip() -> None:
    """test_encrypt_unicode_plaintext_roundtrip senaryosunu test eder."""
    unicode_text = "türkçe karakter: şçöğüı"
    assert decrypt_secret(encrypt_secret(unicode_text)) == unicode_text


# ── _generate_backup_codes ────────────────────────────────────────────────────


def test_generate_backup_codes_returns_list_of_eight() -> None:
    """test_generate_backup_codes_returns_list_of_eight senaryosunu test eder."""
    codes = _generate_backup_codes()
    assert len(codes) == 8


def test_generate_backup_codes_all_strings() -> None:
    """test_generate_backup_codes_all_strings senaryosunu test eder."""
    codes = _generate_backup_codes()
    assert all(isinstance(c, str) for c in codes)


def test_generate_backup_codes_all_uppercase_hex() -> None:
    """Her kod 8 büyük hex karakterden oluşmalı (token_hex(4) → 8 char)."""
    codes = _generate_backup_codes()
    for code in codes:
        assert re.fullmatch(r"[0-9A-F]{8}", code), f"Geçersiz kod: {code!r}"


def test_generate_backup_codes_unique_within_set() -> None:
    """test_generate_backup_codes_unique_within_set senaryosunu test eder."""
    codes = _generate_backup_codes()
    assert len(set(codes)) == 8


def test_generate_backup_codes_different_each_call() -> None:
    """test_generate_backup_codes_different_each_call senaryosunu test eder."""
    set1 = set(_generate_backup_codes())
    set2 = set(_generate_backup_codes())
    # 8 rastgele 4-byte hex ile çakışma olasılığı ihmal edilebilir
    assert set1 != set2


# ── _generate_raw_key ─────────────────────────────────────────────────────────


def test_generate_raw_key_starts_with_prefix() -> None:
    """test_generate_raw_key_starts_with_prefix senaryosunu test eder."""
    assert _generate_raw_key().startswith("sk_live_")


def test_generate_raw_key_correct_total_length() -> None:
    # "sk_live_" (8) + token_hex(40) (80) = 88 karakter
    """test_generate_raw_key_correct_total_length senaryosunu test eder."""
    assert len(_generate_raw_key()) == 88


def test_generate_raw_key_suffix_is_hex() -> None:
    """test_generate_raw_key_suffix_is_hex senaryosunu test eder."""
    key = _generate_raw_key()
    suffix = key[len("sk_live_") :]
    # int() dönüşümü geçerli hex için hata fırlatmaz
    int(suffix, 16)


def test_generate_raw_key_unique_each_call() -> None:
    """test_generate_raw_key_unique_each_call senaryosunu test eder."""
    k1 = _generate_raw_key()
    k2 = _generate_raw_key()
    assert k1 != k2


# ── _split_key ────────────────────────────────────────────────────────────────


def test_split_key_returns_two_elements() -> None:
    """test_split_key_returns_two_elements senaryosunu test eder."""
    key = _generate_raw_key()
    result = _split_key(key)
    assert len(result) == 2


def test_split_key_prefix_is_first_twelve_chars() -> None:
    """test_split_key_prefix_is_first_twelve_chars senaryosunu test eder."""
    key = _generate_raw_key()
    prefix, secret = _split_key(key)
    assert prefix == key[:12]


def test_split_key_secret_is_remainder() -> None:
    """test_split_key_secret_is_remainder senaryosunu test eder."""
    key = _generate_raw_key()
    prefix, secret = _split_key(key)
    assert secret == key[12:]


def test_split_key_roundtrip_with_generated_key() -> None:
    """test_split_key_roundtrip_with_generated_key senaryosunu test eder."""
    raw = _generate_raw_key()
    prefix, secret = _split_key(raw)
    assert prefix + secret == raw
    assert len(prefix) == 12
    assert len(secret) == 76  # 88 - 12
