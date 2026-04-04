"""Security modülü unit testleri."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.exceptions import InvalidTokenError, TokenExpiredError
from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_token,
    hash_password,
    verify_password,
)

# ── Password Hashing ──────────────────────────────────────────────────────────


def test_hash_password_returns_different_hash_each_time():
    """test_hash_password_returns_different_hash_each_time senaryosunu test eder."""
    pw = "TestPassword1"
    h1 = hash_password(pw)
    h2 = hash_password(pw)
    assert h1 != h2  # bcrypt salt farklı olmalı


def test_verify_password_correct():
    """test_verify_password_correct senaryosunu test eder."""
    pw = "TestPassword1"
    hashed = hash_password(pw)
    assert verify_password(pw, hashed) is True


def test_verify_password_wrong():
    """test_verify_password_wrong senaryosunu test eder."""
    hashed = hash_password("TestPassword1")
    assert verify_password("WrongPassword1", hashed) is False


def test_token_type_values():
    """test_token_type_values senaryosunu test eder."""
    assert TokenType.ACCESS == "access"
    assert TokenType.REFRESH == "refresh"


# ── JWT Token ─────────────────────────────────────────────────────────────────


def test_create_access_token_decode_roundtrip():
    """Access token oluşturup decode etmek payload'ı doğru dönmeli."""
    user_id = "550e8400-e29b-41d4-a716-446655440000"
    token = create_access_token(user_id)
    payload = decode_token(token)

    assert payload.sub == user_id
    assert payload.type == TokenType.ACCESS
    assert payload.jti  # UUID string, boş olmamalı
    assert payload.iat is not None
    assert payload.exp > payload.iat


def test_create_refresh_token_decode_roundtrip():
    """Refresh token oluşturup decode etmek doğru type döndürmeli."""
    user_id = "550e8400-e29b-41d4-a716-446655440001"
    token, jti = create_refresh_token(user_id)
    payload = decode_token(token)

    assert payload.sub == user_id
    assert payload.type == TokenType.REFRESH
    assert payload.jti == jti  # Dönen jti ile payload içindeki eşleşmeli


def test_create_token_pair_has_required_keys():
    """create_token_pair access_token, refresh_token ve token_type döndürmeli."""
    result = create_token_pair("some-user-id")

    assert "access_token" in result
    assert "refresh_token" in result
    assert result["token_type"] == "bearer"

    # Her iki token da decode edilebilmeli
    access_payload = decode_token(result["access_token"])
    refresh_payload = decode_token(result["refresh_token"])
    assert access_payload.type == TokenType.ACCESS
    assert refresh_payload.type == TokenType.REFRESH


def test_decode_expired_token_raises_token_expired_error():
    """Süresi dolmuş token TokenExpiredError fırlatmalı."""
    token = create_access_token("user-123", expires_delta=timedelta(seconds=-1))
    with pytest.raises(TokenExpiredError):
        decode_token(token)


def test_decode_tampered_token_raises_invalid_token_error():
    """İmzası bozulmuş token InvalidTokenError fırlatmalı."""
    token = create_access_token("user-123")
    # Son 5 karakteri değiştirerek imzayı boz
    tampered = token[:-5] + "XXXXX"
    with pytest.raises(InvalidTokenError):
        decode_token(tampered)


def test_decode_completely_invalid_string_raises_invalid_token_error():
    """Rastgele string decode edilmeye çalışılırsa InvalidTokenError fırlatmalı."""
    with pytest.raises(InvalidTokenError):
        decode_token("not.a.jwt.token.at.all")
