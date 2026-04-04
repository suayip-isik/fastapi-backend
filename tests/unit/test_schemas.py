"""Auth şema validator'ları için unit testler."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.schemas.auth import RegisterRequest, ResetPasswordRequest, validate_password_strength

# ── validate_password_strength ────────────────────────────────────────────────


def test_validate_password_strength_valid_returns_unchanged() -> None:
    """test_validate_password_strength_valid_returns_unchanged senaryosunu test eder."""
    assert validate_password_strength("StrongPass1") == "StrongPass1"


def test_validate_password_strength_with_special_chars() -> None:
    """test_validate_password_strength_with_special_chars senaryosunu test eder."""
    assert validate_password_strength("StrongPass1!") == "StrongPass1!"


def test_validate_password_strength_missing_uppercase_raises() -> None:
    """test_validate_password_strength_missing_uppercase_raises senaryosunu test eder."""
    with pytest.raises(ValueError, match="büyük harf"):
        validate_password_strength("weakpass1")


def test_validate_password_strength_missing_lowercase_raises() -> None:
    """test_validate_password_strength_missing_lowercase_raises senaryosunu test eder."""
    with pytest.raises(ValueError, match="küçük harf"):
        validate_password_strength("WEAKPASS1")


def test_validate_password_strength_missing_digit_raises() -> None:
    """test_validate_password_strength_missing_digit_raises senaryosunu test eder."""
    with pytest.raises(ValueError, match="rakam"):
        validate_password_strength("WeakPassword")


def test_validate_password_strength_missing_uppercase_and_digit() -> None:
    """Birden fazla eksiklik hata mesajında listelenmeli."""
    with pytest.raises(ValueError) as exc_info:
        validate_password_strength("alllowercase")
    msg = str(exc_info.value)
    assert "büyük harf" in msg
    assert "rakam" in msg


def test_validate_password_strength_all_missing() -> None:
    """Hiçbir kural karşılanmazsa tüm eksiklikler listelenmeli."""
    with pytest.raises(ValueError) as exc_info:
        validate_password_strength("ALLCAPS")
    msg = str(exc_info.value)
    assert "küçük harf" in msg
    assert "rakam" in msg


def test_validate_password_strength_minimum_valid() -> None:
    """8 karakter, büyük harf, küçük harf, rakam — geçerli."""
    assert validate_password_strength("Aa1bbbbb") == "Aa1bbbbb"


def test_validate_password_strength_exact_requirements() -> None:
    """Sadece zorunlu karakterler içeren minimal şifre."""
    assert validate_password_strength("Abcdefg1") == "Abcdefg1"


# ── RegisterRequest ───────────────────────────────────────────────────────────


def test_register_request_valid_data() -> None:
    """test_register_request_valid_data senaryosunu test eder."""
    req = RegisterRequest(email="user@example.com", password="StrongPass1")
    assert req.email == "user@example.com"
    assert req.password == "StrongPass1"


def test_register_request_with_full_name() -> None:
    """test_register_request_with_full_name senaryosunu test eder."""
    req = RegisterRequest(email="user@example.com", password="StrongPass1", full_name="Test User")
    assert req.full_name == "Test User"


def test_register_request_full_name_is_optional() -> None:
    """test_register_request_full_name_is_optional senaryosunu test eder."""
    req = RegisterRequest(email="user@example.com", password="StrongPass1")
    assert req.full_name is None


def test_register_request_password_too_short_raises() -> None:
    """test_register_request_password_too_short_raises senaryosunu test eder."""
    with pytest.raises(PydanticValidationError):
        RegisterRequest(email="a@b.com", password="Sh0rt")


def test_register_request_password_too_long_raises() -> None:
    """test_register_request_password_too_long_raises senaryosunu test eder."""
    with pytest.raises(PydanticValidationError):
        RegisterRequest(email="a@b.com", password="A1" + "x" * 127)  # 129 chars


def test_register_request_password_no_uppercase_raises() -> None:
    """test_register_request_password_no_uppercase_raises senaryosunu test eder."""
    with pytest.raises(PydanticValidationError):
        RegisterRequest(email="a@b.com", password="weakpass1")


def test_register_request_password_no_digit_raises() -> None:
    """test_register_request_password_no_digit_raises senaryosunu test eder."""
    with pytest.raises(PydanticValidationError):
        RegisterRequest(email="a@b.com", password="WeakPassword")


def test_register_request_password_no_lowercase_raises() -> None:
    """test_register_request_password_no_lowercase_raises senaryosunu test eder."""
    with pytest.raises(PydanticValidationError):
        RegisterRequest(email="a@b.com", password="WEAKPASS1")


def test_register_request_invalid_email_raises() -> None:
    """test_register_request_invalid_email_raises senaryosunu test eder."""
    with pytest.raises(PydanticValidationError):
        RegisterRequest(email="not-an-email", password="StrongPass1")


def test_register_request_full_name_too_long_raises() -> None:
    """test_register_request_full_name_too_long_raises senaryosunu test eder."""
    with pytest.raises(PydanticValidationError):
        RegisterRequest(email="a@b.com", password="StrongPass1", full_name="x" * 256)


def test_register_request_full_name_max_length_accepted() -> None:
    """test_register_request_full_name_max_length_accepted senaryosunu test eder."""
    req = RegisterRequest(email="a@b.com", password="StrongPass1", full_name="x" * 255)
    assert len(req.full_name) == 255  # type: ignore[arg-type]


def test_register_request_password_exactly_8_chars_accepted() -> None:
    """test_register_request_password_exactly_8_chars_accepted senaryosunu test eder."""
    req = RegisterRequest(email="a@b.com", password="StrongP1")
    assert req.password == "StrongP1"


def test_register_request_password_exactly_128_chars_accepted() -> None:
    # 128 karakter: büyük harf + rakam + küçük harfler
    """test_register_request_password_exactly_128_chars_accepted senaryosunu test eder."""
    password = "A1" + "x" * 126  # 128 chars
    req = RegisterRequest(email="a@b.com", password=password)
    assert len(req.password) == 128


# ── ResetPasswordRequest ──────────────────────────────────────────────────────


def test_reset_password_request_valid_data() -> None:
    """test_reset_password_request_valid_data senaryosunu test eder."""
    req = ResetPasswordRequest(token="some-reset-token", new_password="NewPass1")
    assert req.token == "some-reset-token"
    assert req.new_password == "NewPass1"


def test_reset_password_request_new_password_validated_for_strength() -> None:
    """test_reset_password_request_new_password_validated_for_strength senaryosunu test eder."""
    with pytest.raises(PydanticValidationError):
        ResetPasswordRequest(token="token", new_password="weakpass1")


def test_reset_password_request_new_password_too_short_raises() -> None:
    """test_reset_password_request_new_password_too_short_raises senaryosunu test eder."""
    with pytest.raises(PydanticValidationError):
        ResetPasswordRequest(token="token", new_password="Sh0rt")


def test_reset_password_request_new_password_no_digit_raises() -> None:
    """test_reset_password_request_new_password_no_digit_raises senaryosunu test eder."""
    with pytest.raises(PydanticValidationError):
        ResetPasswordRequest(token="token", new_password="WeakPassword")


def test_reset_password_request_new_password_no_uppercase_raises() -> None:
    """test_reset_password_request_new_password_no_uppercase_raises senaryosunu test eder."""
    with pytest.raises(PydanticValidationError):
        ResetPasswordRequest(token="token", new_password="weakpass1")


def test_reset_password_request_token_can_be_any_string() -> None:
    """test_reset_password_request_token_can_be_any_string senaryosunu test eder."""
    req = ResetPasswordRequest(token="abc123-xyz", new_password="StrongPass1")
    assert req.token == "abc123-xyz"
