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

from app.core.i18n import t
from app.core.logging import get_logger, request_id_var

_logger = get_logger(__name__)


# ── Base ──────────────────────────────────────────────────────────────────────


class AppError(Exception):
    """Tüm uygulama exception'larının base sınıfı.

    Merkezi exception handling için kullanılır. Her exception message,
    HTTP status code ve opsiyonel details içerir. Global exception
    handler bu sınıfı yakalayıp JSON response döner.

    Attributes:
        status_code: HTTP status code (varsayılan 500)
        code: Hata kodu string (API response'unda kullanılır)
        message: Kullanıcıya gösterilecek hata mesajı
        details: Ek hata detayları (dict, list, vb.)

    Args:
        message: Özel hata mesajı (None ise class message kullanılır)
        details: Ek detay bilgisi (validation errors, context vb.)

    Example:
        >>> raise AppError("Bir şeyler ters gitti", details={"field": "value"})
        >>> raise AppError()  # Class message kullanır
    """

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "INTERNAL_ERROR"
    message: str = "Beklenmeyen bir hata oluştu."
    message_key: str = "error.internal"

    def __init__(self, message: str | None = None, details: Any = None):
        """AppError nesnesini olusturur."""
        self._custom_message = message  # None ise class default kullanılır
        self.message = message or self.__class__.message
        self.details = details
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Hata nesnesini standart API error formatina cevirir."""
        rid = request_id_var.get()
        # Özel mesaj varsa (service katmanından t() ile gelir), direkt kullan.
        # Yoksa class message_key üzerinden çevir.
        if self._custom_message is not None:
            msg = self._custom_message
        else:
            msg = t(self.__class__.message_key)
        return {
            "error": {
                "code": self.code,
                "message": msg,
                "request_id": rid if rid != "-" else None,
                **({"details": self.details} if self.details else {}),
            }
        }


# ── Auth Errors ───────────────────────────────────────────────────────────────


class AuthenticationError(AppError):
    """Kimlik doğrulama başarısız olduğunda fırlatılır.

    Token geçersiz, süresi dolmuş veya kullanıcı credential'ları
    hatalı olduğunda kullanılır. Tüm auth hatalarının parent sınıfı.

    Note:
        HTTP 401 Unauthorized döner.
    """

    status_code = status.HTTP_401_UNAUTHORIZED
    code = "AUTHENTICATION_FAILED"
    message = "Kimlik doğrulama başarısız."
    message_key = "error.auth.failed"


class InvalidTokenError(AuthenticationError):
    """JWT token geçersiz veya parse edilemediğinde fırlatılır.

    Token signature doğrulanamadığında, format hatalıysa veya
    gerekli claim'ler eksikse bu exception fırlatılır.

    Note:
        - HTTP 401 Unauthorized döner
        - Token expired için TokenExpiredError kullanın
        - decode_token() fonksiyonu tarafından fırlatılır
    """

    code = "INVALID_TOKEN"
    message = "Geçersiz token."
    message_key = "error.auth.invalid_token"


class TokenExpiredError(AuthenticationError):
    """JWT token'ın exp claim'i geçmişte olduğunda fırlatılır.

    Access token veya refresh token süresi dolduğunda kullanılır.
    Client yeni token almak için refresh endpoint'ine istek atmalı.

    Note:
        HTTP 401 Unauthorized döner.

    Example:
        >>> # Token 30 dakika sonra expire olur
        >>> raise TokenExpiredError("Access token süresi dolmuş")
    """

    code = "TOKEN_EXPIRED"
    message = "Token süresi dolmuş."
    message_key = "error.auth.token_expired"


class InsufficientPermissionsError(AppError):
    """Kullanıcının işlem için gerekli role/permission'ı yoksa fırlatılır.

    Kimlik doğrulanmış fakat yetkisiz kullanıcılar için kullanılır.
    surface/permission dependency'leri tarafından fırlatılır.

    Note:
        - HTTP 403 Forbidden döner
        - 401 (AuthenticationError) ile karıştırılmamalı
        - User authenticated ama authorized değil

    Example:
        >>> # User role: USER, Required: ADMIN
        >>> raise InsufficientPermissionsError("Admin yetkisi gerekli")
    """

    status_code = status.HTTP_403_FORBIDDEN
    code = "INSUFFICIENT_PERMISSIONS"
    message = "Bu işlem için yetkiniz yok."
    message_key = "error.auth.insufficient_permissions"


# ── Resource Errors ───────────────────────────────────────────────────────────


class NotFoundError(AppError):
    """İstenen kaynak veritabanında bulunamadığında fırlatılır.

    Repository get() veya service katmanında kaynak yoksa kullanılır.
    Domain-specific subclass'lar (UserNotFoundError vb.) tercih edilir.

    Note:
        HTTP 404 Not Found döner.

    Example:
        >>> raise NotFoundError("ID: 123 kaynağı bulunamadı")
    """

    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"
    message = "Kaynak bulunamadı."
    message_key = "error.not_found"


class AlreadyExistsError(AppError):
    """Unique constraint ihlali veya duplicate kaynak oluşturma denemesi.

    Email, username gibi unique alanlar çakıştığında kullanılır.
    Database UNIQUE constraint violation'ları için yaygın exception.

    Note:
        HTTP 409 Conflict döner.

    Example:
        >>> raise AlreadyExistsError("Bu email zaten kayıtlı")
    """

    status_code = status.HTTP_409_CONFLICT
    code = "ALREADY_EXISTS"
    message = "Bu kaynak zaten mevcut."
    message_key = "error.already_exists"


# ── Validation / Business ─────────────────────────────────────────────────────


class ValidationError(AppError):
    """Business-layer validation hatası (Pydantic dışı).

    Pydantic schema validation geçmiş ama business rules ihlal edilmiş
    girdiler için kullanılır. Örn: tarih aralığı mantık hatası, value
    range kontrolü vb.

    Note:
        - HTTP 422 Unprocessable Entity döner
        - Pydantic validation FastAPI tarafından otomatik handle edilir
        - Bu exception manuel business validation için

    Example:
        >>> if start_date > end_date:
        ...     raise ValidationError("Başlangıç tarihi bitiş tarihinden sonra olamaz")
    """

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "VALIDATION_ERROR"
    message = "Girdi doğrulama hatası."
    message_key = "error.validation"


class BusinessRuleError(AppError):
    """Domain-specific iş kuralı ihlali.

    Kullanıcı geçerli bir request yapmış ancak business logic kuralları
    nedeniyle işlem gerçekleştirilemiyor. Örn: bakiye yetersiz, stok yok,
    aksiyon için state uygun değil.

    Note:
        HTTP 400 Bad Request döner.

    Example:
        >>> if user.balance < amount:
        ...     raise BusinessRuleError("Yetersiz bakiye")
        >>> if product.stock == 0:
        ...     raise BusinessRuleError("Stokta yok")
    """

    status_code = status.HTTP_400_BAD_REQUEST
    code = "BUSINESS_RULE_VIOLATION"
    message = "İş kuralı ihlali."
    message_key = "error.business_rule"


# ── External / Infrastructure ─────────────────────────────────────────────────


class ExternalServiceError(AppError):
    """Dış servis (API, webhook vb.) çağrısı başarısız olduğunda fırlatılır.

    Payment gateway, email service gibi external API'ler
    timeout, 5xx error veya network hatası verdiğinde kullanılır.

    Note:
        - HTTP 502 Bad Gateway döner
        - Retry stratejisi için ARQ task kullanılabilir
        - Circuit breaker pattern önerilir

    Example:
        >>> raise ExternalServiceError("Email servisi yanıt vermiyor")
    """

    status_code = status.HTTP_502_BAD_GATEWAY
    code = "EXTERNAL_SERVICE_ERROR"
    message = "Dış servis hatası."
    message_key = "error.external_service"


class ConfigurationError(AppError):
    """Uygulama config hatası (env var eksik, geçersiz değer vb.).

    Settings validation hatası veya runtime config problemi için
    kullanılır. Genellikle startup sırasında fırlatılır.

    Note:
        - HTTP 500 Internal Server Error döner
        - Production'da bu hata olmamalı (CI/CD catch etmeli)
        - .env.example ile senkron tutulmalı

    Example:
        >>> if not settings.SECRET_KEY:
        ...     raise ConfigurationError("SECRET_KEY environment variable gerekli")
    """

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "CONFIGURATION_ERROR"
    message = "Uygulama yapılandırma hatası."
    message_key = "error.configuration"


# ── Storage ───────────────────────────────────────────────────────────────────


class StorageError(AppError):
    """S3/MinIO dosya storage işlemi başarısız olduğunda fırlatılır.

    Upload, download, delete işlemlerinde S3 client hataları için
    kullanılır. Network, permission veya bucket hatalarını kapsar.

    Note:
        - HTTP 500 Internal Server Error döner
        - StorageService tarafından fırlatılır
        - Client hatası değil, sunucu tarafı storage problemi

    Example:
        >>> raise StorageError("MinIO bucket erişim hatası", details={"bucket": "uploads"})
    """

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "STORAGE_ERROR"
    message = "Dosya depolama hatası."
    message_key = "error.storage"


class FileTooLargeError(AppError):
    """Upload edilen dosya max_size limitini aştığında fırlatılır.

    Config'de tanımlı MAX_FILE_SIZE değerinden büyük dosyalar için
    kullanılır. Genellikle file upload middleware'inde kontrol edilir.

    Note:
        HTTP 413 Request Entity Too Large döner.

    Example:
        >>> # MAX_FILE_SIZE = 10MB
        >>> if file.size > 10 * 1024 * 1024:
        ...     raise FileTooLargeError(f"Max 10MB, gönderilen: {file.size}")
    """

    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    code = "FILE_TOO_LARGE"
    message = "Dosya boyutu çok büyük."
    message_key = "error.file_too_large"


class InvalidFileTypeError(AppError):
    """Upload edilen dosya türü allowed_types listesinde değilse fırlatılır.

    MIME type veya file extension kontrolü başarısız olduğunda kullanılır.
    Güvenlik için önemli - executable veya tehlikeli dosyaları engeller.

    Note:
        HTTP 415 Unsupported Media Type döner.

    Example:
        >>> allowed = ["image/jpeg", "image/png"]
        >>> if file.content_type not in allowed:
        ...     raise InvalidFileTypeError(f"İzin verilen: {allowed}")
    """

    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    code = "INVALID_FILE_TYPE"
    message = "Desteklenmeyen dosya türü."
    message_key = "error.invalid_file_type"


# ── Rate Limit ────────────────────────────────────────────────────────────────


class RateLimitError(AppError):
    """Rate limit aşıldığında fırlatılır.

    Redis-based rate limiting middleware tarafından kullanılır.
    IP veya user bazlı istek sınırlaması için fırlatılır.

    Note:
        - HTTP 429 Too Many Requests döner
        - Response header'da Retry-After bilgisi olmalı
        - rate_limit() middleware tarafından handle edilir

    Example:
        >>> # 100 req/min limit aşıldı
        >>> raise RateLimitError("Dakikada max 100 istek", details={"retry_after": 60})
    """

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "RATE_LIMIT_EXCEEDED"
    message = "Çok fazla istek gönderildi. Lütfen bekleyin."
    message_key = "error.rate_limit"


# ── Domain-Specific Subclasses ────────────────────────────────────────────────


class UserNotFoundError(NotFoundError):
    """User ID veya email ile kullanıcı bulunamadığında fırlatılır.

    UserRepository.get() veya UserService metodları tarafından fırlatılır.
    Generic NotFoundError yerine bu specific exception tercih edilir.

    Note:
        HTTP 404 Not Found döner.

    Example:
        >>> user = await repo.get(user_id)
        >>> if not user:
        ...     raise UserNotFoundError(f"User ID: {user_id}")
    """

    code = "USER_NOT_FOUND"
    message = "Kullanıcı bulunamadı."
    message_key = "error.user.not_found"


class UserAlreadyExistsError(AlreadyExistsError):
    """Aynı email ile kullanıcı zaten kayıtlı ise fırlatılır.

    User registration sırasında email unique constraint violation
    olduğunda kullanılır. UserService.register() tarafından fırlatılır.

    Note:
        HTTP 409 Conflict döner.

    Example:
        >>> existing = await repo.get_by_email(email)
        >>> if existing:
        ...     raise UserAlreadyExistsError(f"Email: {email}")
    """

    code = "USER_ALREADY_EXISTS"
    message = "Bu e-posta adresi zaten kayıtlı."
    message_key = "error.user.already_exists"


class UserDeletedError(AuthenticationError):
    """Soft-deleted kullanıcı login yapmaya çalıştığında fırlatılır.

    User.deleted_at IS NOT NULL olan hesaplar için authentication
    reddedilir. get_current_user() dependency tarafından kontrol edilir.

    Note:
        - HTTP 401 Unauthorized döner
        - Soft delete: is_deleted=True veya deleted_at!=None
        - Hard delete'de user zaten NotFoundError verir

    Example:
        >>> if user.deleted_at:
        ...     raise UserDeletedError()
    """

    code = "USER_DELETED"
    message = "Bu hesap silinmiş."
    message_key = "error.user.deleted"


class APIKeyNotFoundError(NotFoundError):
    """API key ID ile kayıt bulunamadığında fırlatılır.

    APIKeyRepository.get() veya user'ın API key'leri arasında
    arama yapılırken kullanılır.

    Note:
        HTTP 404 Not Found döner.

    Example:
        >>> key = await repo.get(key_id)
        >>> if not key:
        ...     raise APIKeyNotFoundError(f"API Key ID: {key_id}")
    """

    code = "API_KEY_NOT_FOUND"
    message = "API anahtarı bulunamadı."
    message_key = "error.api_key.not_found"


class TOTPNotConfiguredError(BusinessRuleError):
    """2FA gerekli bir işlemde user TOTP enable etmemişse fırlatılır.

    User.totp_secret NULL iken TOTP verification gerekli endpoint'lere
    erişim denemesinde kullanılır.

    Note:
        HTTP 400 Bad Request döner.

    Example:
        >>> if not user.totp_secret:
        ...     raise TOTPNotConfiguredError("Önce 2FA'yı etkinleştirin")
    """

    code = "TOTP_NOT_CONFIGURED"
    message = "2FA yapılandırılmamış."
    message_key = "error.totp.not_configured"


class TOTPAlreadyEnabledError(BusinessRuleError):
    """2FA enable edilmişken tekrar enable denemesi yapılırsa fırlatılır.

    User.totp_secret zaten set iken /totp/enable endpoint'ine istek
    atıldığında kullanılır. Duplicate configuration önlenir.

    Note:
        HTTP 400 Bad Request döner.

    Example:
        >>> if user.totp_secret:
        ...     raise TOTPAlreadyEnabledError()
    """

    code = "TOTP_ALREADY_ENABLED"
    message = "2FA zaten aktif."
    message_key = "error.totp.already_enabled"


# ── Helpers ───────────────────────────────────────────────────────────────────


_VALIDATION_TYPE_KEYS: dict[str, str] = {
    "missing": "validation.missing",
    "string_type": "validation.string_type",
    "int_type": "validation.int_type",
    "float_type": "validation.float_type",
    "bool_type": "validation.bool_type",
    "value_error": "validation.value_error",
    "string_too_short": "validation.string_too_short",
    "string_too_long": "validation.string_too_long",
    "greater_than": "validation.greater_than",
    "greater_than_equal": "validation.greater_than_equal",
    "less_than": "validation.less_than",
    "less_than_equal": "validation.less_than_equal",
    "list_type": "validation.list_type",
    "url_parsing": "validation.url_parsing",
    "url_type": "validation.url_type",
    "datetime_type": "validation.datetime_type",
    "uuid_type": "validation.uuid_type",
    "enum": "validation.enum",
}


def _serialize_validation_errors(errors: list[Any]) -> list[dict[str, Any]]:
    """Pydantic validation hatalarını JSON-serializable formata çevirir.

    FastAPI RequestValidationError içindeki Pydantic error dict'lerini
    client-friendly formata dönüştürür. Field path, message ve type içerir.
    Bilinen error type'lar için çevrilmiş mesaj kullanılır.

    Args:
        errors: Pydantic ValidationError.errors() listesi

    Returns:
        JSON-serializable error dict listesi
    """
    result = []
    for error in errors:
        error_type = str(error.get("type", ""))
        translation_key = _VALIDATION_TYPE_KEYS.get(error_type)
        message = t(translation_key) if translation_key else str(error.get("msg", ""))
        result.append(
            {
                "field": " -> ".join(str(loc) for loc in error.get("loc", [])),
                "message": message,
                "type": error_type,
            }
        )
    return result


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
) -> JSONResponse:
    """Standart error response JSON objesi oluşturur.

    Exception handler'lar tarafından kullanılır. Tutarlı error format
    sağlar: {error: {code, message, request_id, details?}}.

    Args:
        status_code: HTTP status code
        code: Error code string (VALIDATION_ERROR, NOT_FOUND vb.)
        message: Kullanıcıya gösterilecek mesaj
        details: Opsiyonel ek detaylar (dict/list)

    Returns:
        FastAPI JSONResponse objesi

    Example:
        >>> return _error_response(404, "NOT_FOUND", "Kaynak bulunamadı")
    """
    rid = request_id_var.get()
    content: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "request_id": rid if rid != "-" else None,
        }
    }
    if details is not None:
        content["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=content)


# ── Exception Handlers ────────────────────────────────────────────────────────


def register_exception_handlers(app: FastAPI) -> None:
    """Global exception handler'ları FastAPI app'e register eder.

    Tüm exception'ları yakalar ve tutarlı JSON response döner.
    AppError, HTTPException, ValidationError ve unhandled exceptions
    için handler tanımlar.

    Args:
        app: FastAPI application instance

    Note:
        - main.py'da startup sırasında çağrılmalı
        - Handler priority: specific -> generic
        - Unhandled exceptions loglanır + 500 döner

    Example:
        >>> app = FastAPI()
        >>> register_exception_handlers(app)
    """

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        """Uygulama-ozel hatalari JSON formatinda dondurur."""
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """FastAPI/Starlette HTTPException hatalarini normalize eder."""
        return _error_response(exc.status_code, "HTTP_ERROR", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Request validation hatalarini detayli sekilde dondurur."""
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "VALIDATION_ERROR",
            t("error.validation.request"),
            details=_serialize_validation_errors(list(exc.errors())),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        """Beklenmeyen hatalari loglayip generic 500 doner."""
        _logger.error(
            "unhandled_exception",
            method=request.method,
            path=request.url.path,
            exc_type=type(exc).__name__,
            exc_info=True,
        )
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            t("error.internal"),
        )
