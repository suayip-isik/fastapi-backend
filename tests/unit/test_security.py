"""Security modülü unit testleri."""
from __future__ import annotations

import pytest
from unittest.mock import patch, mock_open

from app.core.security import (
    hash_password,
    verify_password,
    TokenType,
)


def test_hash_password_returns_different_hash_each_time():
    pw = "TestPassword1"
    h1 = hash_password(pw)
    h2 = hash_password(pw)
    assert h1 != h2  # bcrypt salt farklı olmalı


def test_verify_password_correct():
    pw = "TestPassword1"
    hashed = hash_password(pw)
    assert verify_password(pw, hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("TestPassword1")
    assert verify_password("WrongPassword1", hashed) is False


def test_token_type_values():
    assert TokenType.ACCESS == "access"
    assert TokenType.REFRESH == "refresh"
