"""Exception hiyerarşisi ve yardımcı fonksiyon unit testleri."""

from __future__ import annotations

import json

import pytest
from fastapi import status

from app.core.exceptions import (
    AlreadyExistsError,
    AppError,
    AuthenticationError,
    BusinessRuleError,
    FileTooLargeError,
    InsufficientPermissionsError,
    InvalidFileTypeError,
    InvalidTokenError,
    NotFoundError,
    RateLimitError,
    StorageError,
    TokenExpiredError,
    ValidationError,
    _error_response,
    _serialize_validation_errors,
)


# ── AppError Base ─────────────────────────────────────────────────────────────


def test_app_error_default_attributes() -> None:
    err = AppError()
    assert err.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert err.code == "INTERNAL_ERROR"
    assert err.message == "Beklenmeyen bir hata oluştu."
    assert isinstance(err, Exception)


def test_app_error_custom_message_overrides_default() -> None:
    err = AppError("Custom error message")
    assert err.message == "Custom error message"
    assert str(err) == "Custom error message"


def test_app_error_to_dict_without_details() -> None:
    err = AppError("Some error")
    d = err.to_dict()
    assert d == {"error": {"code": "INTERNAL_ERROR", "message": "Some error"}}
    assert "details" not in d["error"]


def test_app_error_to_dict_with_details() -> None:
    err = AppError("Some error", details={"field": "email"})
    d = err.to_dict()
    assert d["error"]["details"] == {"field": "email"}


def test_app_error_to_dict_details_none_excluded() -> None:
    err = AppError("Some error", details=None)
    assert "details" not in err.to_dict()["error"]


def test_app_error_to_dict_details_can_be_list() -> None:
    err = AppError("Some error", details=[{"field": "x"}, {"field": "y"}])
    assert isinstance(err.to_dict()["error"]["details"], list)
    assert len(err.to_dict()["error"]["details"]) == 2


def test_app_error_to_dict_contains_code_and_message_keys() -> None:
    err = AppError()
    d = err.to_dict()
    assert "error" in d
    assert "code" in d["error"]
    assert "message" in d["error"]


# ── Exception Hierarchy ───────────────────────────────────────────────────────


def test_authentication_error_inherits_app_error() -> None:
    assert issubclass(AuthenticationError, AppError)
    assert AuthenticationError.status_code == status.HTTP_401_UNAUTHORIZED
    assert AuthenticationError.code == "AUTHENTICATION_FAILED"


def test_invalid_token_error_inherits_authentication_error() -> None:
    assert issubclass(InvalidTokenError, AuthenticationError)
    assert InvalidTokenError.status_code == status.HTTP_401_UNAUTHORIZED
    assert InvalidTokenError.code == "INVALID_TOKEN"


def test_token_expired_error_inherits_authentication_error() -> None:
    assert issubclass(TokenExpiredError, AuthenticationError)
    assert TokenExpiredError.status_code == status.HTTP_401_UNAUTHORIZED
    assert TokenExpiredError.code == "TOKEN_EXPIRED"


def test_insufficient_permissions_error() -> None:
    assert issubclass(InsufficientPermissionsError, AppError)
    assert InsufficientPermissionsError.status_code == status.HTTP_403_FORBIDDEN
    assert InsufficientPermissionsError.code == "INSUFFICIENT_PERMISSIONS"


def test_not_found_error() -> None:
    assert issubclass(NotFoundError, AppError)
    assert NotFoundError.status_code == status.HTTP_404_NOT_FOUND
    assert NotFoundError.code == "NOT_FOUND"


def test_already_exists_error() -> None:
    assert issubclass(AlreadyExistsError, AppError)
    assert AlreadyExistsError.status_code == status.HTTP_409_CONFLICT
    assert AlreadyExistsError.code == "ALREADY_EXISTS"


def test_validation_error() -> None:
    assert issubclass(ValidationError, AppError)
    assert ValidationError.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert ValidationError.code == "VALIDATION_ERROR"


def test_business_rule_error() -> None:
    assert issubclass(BusinessRuleError, AppError)
    assert BusinessRuleError.status_code == status.HTTP_400_BAD_REQUEST
    assert BusinessRuleError.code == "BUSINESS_RULE_VIOLATION"


def test_storage_error() -> None:
    assert issubclass(StorageError, AppError)
    assert StorageError.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert StorageError.code == "STORAGE_ERROR"


def test_file_too_large_error() -> None:
    assert issubclass(FileTooLargeError, AppError)
    assert FileTooLargeError.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    assert FileTooLargeError.code == "FILE_TOO_LARGE"


def test_invalid_file_type_error() -> None:
    assert issubclass(InvalidFileTypeError, AppError)
    assert InvalidFileTypeError.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    assert InvalidFileTypeError.code == "INVALID_FILE_TYPE"


def test_rate_limit_error() -> None:
    assert issubclass(RateLimitError, AppError)
    assert RateLimitError.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert RateLimitError.code == "RATE_LIMIT_EXCEEDED"


def test_exceptions_are_catchable_as_app_error() -> None:
    """Tüm alt sınıflar AppError olarak yakalanabilmeli."""
    for exc_class in [
        AuthenticationError,
        InvalidTokenError,
        TokenExpiredError,
        InsufficientPermissionsError,
        NotFoundError,
        AlreadyExistsError,
        ValidationError,
        BusinessRuleError,
        StorageError,
        FileTooLargeError,
        InvalidFileTypeError,
        RateLimitError,
    ]:
        with pytest.raises(AppError):
            raise exc_class()


def test_exception_custom_message_preserved() -> None:
    err = NotFoundError("Kullanıcı bulunamadı.")
    assert err.message == "Kullanıcı bulunamadı."
    assert err.to_dict()["error"]["message"] == "Kullanıcı bulunamadı."


# ── _serialize_validation_errors ─────────────────────────────────────────────


def test_serialize_validation_errors_empty_list() -> None:
    assert _serialize_validation_errors([]) == []


def test_serialize_validation_errors_single_error() -> None:
    error = {
        "loc": ("body", "email"),
        "msg": "value is not a valid email address",
        "type": "value_error.email",
    }
    result = _serialize_validation_errors([error])
    assert len(result) == 1
    assert result[0]["field"] == "body -> email"
    assert result[0]["message"] == "value is not a valid email address"
    assert result[0]["type"] == "value_error.email"


def test_serialize_validation_errors_nested_loc() -> None:
    error = {"loc": ("body", "nested", "field"), "msg": "required", "type": "missing"}
    result = _serialize_validation_errors([error])
    assert result[0]["field"] == "body -> nested -> field"


def test_serialize_validation_errors_missing_loc_key() -> None:
    error = {"msg": "some error", "type": "x"}
    result = _serialize_validation_errors([error])
    assert result[0]["field"] == ""  # boş join


def test_serialize_validation_errors_multiple_errors() -> None:
    errors = [
        {"loc": ("body", "email"), "msg": "invalid email", "type": "value_error"},
        {"loc": ("body", "password"), "msg": "too short", "type": "value_error"},
    ]
    result = _serialize_validation_errors(errors)
    assert len(result) == 2
    assert result[0]["field"] == "body -> email"
    assert result[1]["field"] == "body -> password"


def test_serialize_validation_errors_loc_with_int_indices() -> None:
    """Pydantic bazen loc'ta integer index kullanır (list items için)."""
    error = {"loc": ("body", "items", 0, "name"), "msg": "required", "type": "missing"}
    result = _serialize_validation_errors([error])
    assert result[0]["field"] == "body -> items -> 0 -> name"


# ── _error_response ───────────────────────────────────────────────────────────


def test_error_response_returns_correct_status_code() -> None:
    resp = _error_response(404, "NOT_FOUND", "Not found")
    assert resp.status_code == 404


def test_error_response_body_contains_code_and_message() -> None:
    resp = _error_response(404, "NOT_FOUND", "Not found")
    body = json.loads(resp.body)
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["message"] == "Not found"


def test_error_response_includes_details_when_provided() -> None:
    resp = _error_response(422, "VALIDATION_ERROR", "Bad input", details=[{"field": "x"}])
    body = json.loads(resp.body)
    assert body["error"]["details"] == [{"field": "x"}]


def test_error_response_excludes_details_when_none() -> None:
    resp = _error_response(400, "X", "msg", details=None)
    body = json.loads(resp.body)
    assert "details" not in body["error"]


def test_error_response_details_can_be_dict() -> None:
    resp = _error_response(500, "INTERNAL_ERROR", "error", details={"key": "value"})
    body = json.loads(resp.body)
    assert body["error"]["details"] == {"key": "value"}


def test_error_response_various_status_codes() -> None:
    for code in [400, 401, 403, 404, 409, 413, 415, 422, 429, 500]:
        resp = _error_response(code, "TEST", "test message")
        assert resp.status_code == code
