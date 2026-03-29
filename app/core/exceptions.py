"""
Global exception hierarchy.
Tüm uygulama hataları buradan türetilir — tutarlı API hata formatı sağlar.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

_logger = get_logger(__name__)


# ── Base ──────────────────────────────────────────────────────────────────────


class AppError(Exception):
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "INTERNAL_ERROR"
    message: str = "Beklenmeyen bir hata oluştu."

    def __init__(self, message: str | None = None, details: Any = None):
        self.message = message or self.__class__.message
        self.details = details
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                **({"details": self.details} if self.details else {}),
            }
        }


# ── Auth Errors ───────────────────────────────────────────────────────────────


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "AUTHENTICATION_FAILED"
    message = "Kimlik doğrulama başarısız."


class InvalidTokenError(AuthenticationError):
    code = "INVALID_TOKEN"
    message = "Geçersiz token."


class TokenExpiredError(AuthenticationError):
    code = "TOKEN_EXPIRED"
    message = "Token süresi dolmuş."


class InsufficientPermissionsError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "INSUFFICIENT_PERMISSIONS"
    message = "Bu işlem için yetkiniz yok."


# ── Resource Errors ───────────────────────────────────────────────────────────


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"
    message = "Kaynak bulunamadı."


class AlreadyExistsError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "ALREADY_EXISTS"
    message = "Bu kaynak zaten mevcut."


# ── Validation / Business ─────────────────────────────────────────────────────


class ValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "VALIDATION_ERROR"
    message = "Girdi doğrulama hatası."


class BusinessRuleError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "BUSINESS_RULE_VIOLATION"
    message = "İş kuralı ihlali."


# ── Storage / External ────────────────────────────────────────────────────────


class StorageError(AppError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "STORAGE_ERROR"
    message = "Dosya depolama hatası."


class FileTooLargeError(AppError):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    code = "FILE_TOO_LARGE"
    message = "Dosya boyutu çok büyük."


class InvalidFileTypeError(AppError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    code = "INVALID_FILE_TYPE"
    message = "Desteklenmeyen dosya türü."


# ── Rate Limit ────────────────────────────────────────────────────────────────


class RateLimitError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "RATE_LIMIT_EXCEEDED"
    message = "Çok fazla istek gönderildi. Lütfen bekleyin."


# ── Helpers ───────────────────────────────────────────────────────────────────


def _serialize_validation_errors(errors: list) -> list:
    """Pydantic validation hatalarını JSON-serializable formata çevirir."""
    return [
        {
            "field": " -> ".join(str(loc) for loc in error.get("loc", [])),
            "message": str(error.get("msg", "")),
            "type": str(error.get("type", "")),
        }
        for error in errors
    ]


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
) -> JSONResponse:
    content: dict = {"error": {"code": code, "message": message}}
    if details is not None:
        content["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=content)


# ── Exception Handlers ────────────────────────────────────────────────────────


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error_response(exc.status_code, "HTTP_ERROR", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "VALIDATION_ERROR",
            "İstek doğrulama hatası.",
            details=_serialize_validation_errors(exc.errors()),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        _logger.error(
            "unhandled_exception",
            method=request.method,
            path=request.url.path,
            exc_type=type(exc).__name__,
            exc=str(exc),
            exc_info=exc,
        )
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "Beklenmeyen bir hata oluştu.",
        )
