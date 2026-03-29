"""TOTP ve API Key yardımcı fonksiyonları için unit testler."""

from __future__ import annotations

import re

import pytest
from cryptography.fernet import Fernet

from app.core.exceptions import AuthenticationError
from app.services.api_key import _generate_raw_key, _split_key
from app.services.totp import _decrypt, _encrypt, _generate_backup_codes, _get_fernet


# ── _get_fernet ───────────────────────────────────────────────────────────────


def test_get_fernet_returns_fernet_instance() -> None:
    f = _get_fernet()
    assert isinstance(f, Fernet)


def test_get_fernet_is_deterministic() -> None:
    """Aynı SECRET_KEY'den aynı Fernet anahtarı türetilmeli."""
    f1 = _get_fernet()
    f2 = _get_fernet()
    # f1 ile şifrelenmiş token f2 ile çözülebilmeli
    token = f1.encrypt(b"test-payload")
    assert f2.decrypt(token) == b"test-payload"


# ── _encrypt / _decrypt ───────────────────────────────────────────────────────


def test_encrypt_decrypt_roundtrip() -> None:
    plaintext = "my-secret-totp-key"
    ciphertext = _encrypt(plaintext)
    assert _decrypt(ciphertext) == plaintext


def test_encrypt_produces_different_ciphertext_each_call() -> None:
    """Fernet her şifrelemede rastgele IV kullanır."""
    c1 = _encrypt("same-value")
    c2 = _encrypt("same-value")
    assert c1 != c2


def test_encrypt_returns_str() -> None:
    result = _encrypt("hello")
    assert isinstance(result, str)


def test_decrypt_returns_str() -> None:
    ciphertext = _encrypt("hello")
    result = _decrypt(ciphertext)
    assert isinstance(result, str)


def test_decrypt_wrong_ciphertext_raises_authentication_error() -> None:
    with pytest.raises(AuthenticationError):
        _decrypt("not-valid-fernet-ciphertext")


def test_decrypt_empty_string_raises_authentication_error() -> None:
    with pytest.raises(AuthenticationError):
        _decrypt("")


def test_decrypt_tampered_ciphertext_raises_authentication_error() -> None:
    ciphertext = _encrypt("secret")
    tampered = ciphertext[:-5] + "XXXXX"
    with pytest.raises(AuthenticationError):
        _decrypt(tampered)


def test_encrypt_long_plaintext_roundtrip() -> None:
    long_text = "A" * 1000
    assert _decrypt(_encrypt(long_text)) == long_text


def test_encrypt_unicode_plaintext_roundtrip() -> None:
    unicode_text = "türkçe karakter: şçöğüı"
    assert _decrypt(_encrypt(unicode_text)) == unicode_text


# ── _generate_backup_codes ────────────────────────────────────────────────────


def test_generate_backup_codes_returns_list_of_eight() -> None:
    codes = _generate_backup_codes()
    assert len(codes) == 8


def test_generate_backup_codes_all_strings() -> None:
    codes = _generate_backup_codes()
    assert all(isinstance(c, str) for c in codes)


def test_generate_backup_codes_all_uppercase_hex() -> None:
    """Her kod 8 büyük hex karakterden oluşmalı (token_hex(4) → 8 char)."""
    codes = _generate_backup_codes()
    for code in codes:
        assert re.fullmatch(r"[0-9A-F]{8}", code), f"Geçersiz kod: {code!r}"


def test_generate_backup_codes_unique_within_set() -> None:
    codes = _generate_backup_codes()
    assert len(set(codes)) == 8


def test_generate_backup_codes_different_each_call() -> None:
    set1 = set(_generate_backup_codes())
    set2 = set(_generate_backup_codes())
    # 8 rastgele 4-byte hex ile çakışma olasılığı ihmal edilebilir
    assert set1 != set2


# ── _generate_raw_key ─────────────────────────────────────────────────────────


def test_generate_raw_key_starts_with_prefix() -> None:
    assert _generate_raw_key().startswith("sk_live_")


def test_generate_raw_key_correct_total_length() -> None:
    # "sk_live_" (8) + token_hex(40) (80) = 88 karakter
    assert len(_generate_raw_key()) == 88


def test_generate_raw_key_suffix_is_hex() -> None:
    key = _generate_raw_key()
    suffix = key[len("sk_live_") :]
    # int() dönüşümü geçerli hex için hata fırlatmaz
    int(suffix, 16)


def test_generate_raw_key_unique_each_call() -> None:
    k1 = _generate_raw_key()
    k2 = _generate_raw_key()
    assert k1 != k2


# ── _split_key ────────────────────────────────────────────────────────────────


def test_split_key_returns_two_elements() -> None:
    key = _generate_raw_key()
    result = _split_key(key)
    assert len(result) == 2


def test_split_key_prefix_is_first_twelve_chars() -> None:
    key = _generate_raw_key()
    prefix, secret = _split_key(key)
    assert prefix == key[:12]


def test_split_key_secret_is_remainder() -> None:
    key = _generate_raw_key()
    prefix, secret = _split_key(key)
    assert secret == key[12:]


def test_split_key_roundtrip_with_generated_key() -> None:
    raw = _generate_raw_key()
    prefix, secret = _split_key(raw)
    assert prefix + secret == raw
    assert len(prefix) == 12
    assert len(secret) == 76  # 88 - 12
