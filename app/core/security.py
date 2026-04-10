"""
Security utilities — JWT (RS256), password hashing, token management, symmetric encryption.
RS256 kullanımı: private key ile imzala, public key ile doğrula.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from enum import Enum
from functools import lru_cache
from uuid import uuid4

import bcrypt
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import AuthenticationError, InvalidTokenError, TokenExpiredError


class TokenType(str, Enum):
    """JWT token turlerini temsil eder."""

    ACCESS = "access"
    REFRESH = "refresh"


class TokenPayload(BaseModel):
    """Decode edilmis JWT payload modelidir."""

    sub: str  # user ID
    type: TokenType
    jti: str  # JWT ID (revocation için)
    iat: datetime
    exp: datetime
    scopes: list[str] = []


# ── Symmetric Encryption (Fernet / HKDF) ─────────────────────────────────────


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """
    HKDF ile SECRET_KEY'den deterministik Fernet anahtarı türetir.

    HKDF (RFC 5869) kullanımı, ham SECRET_KEY baytlarını doğrudan kullanmaktan
    veya null-byte dolgusuyla padding yapmaktan daha güvenlidir.

    NOT: SECRET_KEY değiştirilirse mevcut şifrelenmiş değerler okunamaz hale gelir.
    Mevcut kurulumlar için SECRET_KEY sabitlendikten sonra değiştirilmemelidir.
    """
    raw_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"app-symmetric-encryption-v1",
    ).derive(settings.SECRET_KEY.encode())
    return Fernet(base64.urlsafe_b64encode(raw_key))


def encrypt_secret(plaintext: str) -> str:
    """Düz metin değeri Fernet ile şifrele."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    """Fernet ile şifrelenmiş değeri çöz. Geçersizse AuthenticationError fırlatır."""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise AuthenticationError("Şifrelenmiş değer çözümlenemedi.") from exc


# ── Password Hashing ──────────────────────────────────────────────────────────


def hash_password(plain: str) -> str:
    """Düz metin parolayı bcrypt algoritması ile hash'ler.

    Güvenli bir salt üretir (12 rounds) ve parolayı hash'leyerek döndürür.
    Hash'lenmiş parola veritabanında güvenli bir şekilde saklanabilir.

    Args:
        plain: Hash'lenecek düz metin parola

    Returns:
        Base64 encoded bcrypt hash string (UTF-8 decoded)

    Raises:
        ValueError: Parola boş veya geçersiz encoding içeriyorsa

    Example:
        >>> hashed = hash_password("my_secure_password123")
        >>> # $2b$12$KIXQQqLw...

    Note:
        - 12 rounds kullanılır (güvenlik/performans dengesi)
        - Her çağrıda farklı salt üretilir
        - Hash UTF-8 string olarak döndürülür (DB storage için)
    """
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain.encode(), salt).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Düz metin parolayı hash'lenmiş parola ile karşılaştırır.

    Kullanıcı girişi sırasında verilen parolanın veritabanındaki hash ile
    eşleşip eşleşmediğini bcrypt algoritması ile kontrol eder. Timing-safe
    karşılaştırma yapar.

    Args:
        plain: Kullanıcının girdiği düz metin parola
        hashed: Veritabanından alınan hash'lenmiş parola

    Returns:
        True: Parola eşleşiyor
        False: Parola eşleşmiyor

    Example:
        >>> hashed = hash_password("secret123")
        >>> verify_password("secret123", hashed)
        True
        >>> verify_password("wrong", hashed)
        False

    Note:
        - Timing attack'lara karşı güvenli
        - Başarısız doğrulamalar da aynı sürede tamamlanır
        - Encoding hataları False döndürür
    """
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT Token ─────────────────────────────────────────────────────────────────


def create_access_token(
    user_id: str,
    scopes: list[str] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """JWT access token oluşturur (RS256 algoritması).

    Kullanıcı kimlik doğrulaması için kısa ömürlü access token üretir.
    Token type otomatik olarak "access" olarak ayarlanır. Private key ile
    imzalanır, public key ile doğrulanır (asymmetric encryption).

    Args:
        user_id: Token sahibi kullanıcının unique ID'si
        scopes: İsteğe bağlı yetki kapsamları (permissions/roles). Default: []
        expires_delta: Token geçerlilik süresi. None ise ACCESS_TOKEN_EXPIRE_MINUTES kullanılır

    Returns:
        Base64 encoded JWT token string

    Raises:
        JWTError: Token oluşturma sırasında encoding hatası oluşursa

    Example:
        >>> token = create_access_token(user_id="123", scopes=["read:users"])
        >>> # eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
        >>>
        >>> # Custom expiration
        >>> short_token = create_access_token("123", expires_delta=timedelta(minutes=5))

    Note:
        - RS256 (asymmetric) kullanılır, HS256 değil
        - Token type "access" otomatik eklenir
        - Expiration UTC timestamp olarak saklanır
        - Her token unique jti (JWT ID) içerir (revocation için)
        - Default expire: 30 dakika (settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    """
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": str(user_id),
        "type": TokenType.ACCESS,
        "jti": str(uuid4()),
        "iat": datetime.now(UTC),
        "exp": expire,
        "scopes": scopes or [],
    }
    return str(jwt.encode(payload, settings.JWT_PRIVATE_KEY, algorithm="RS256"))


def create_refresh_token(user_id: str) -> tuple[str, str]:
    """Uzun ömürlü refresh token oluşturur (RS256 algoritması).

    Access token yenilemek için kullanılan refresh token üretir. Token ve
    JTI (JWT ID) tuple olarak döner. JTI veritabanında saklanmalı ve token
    revocation için kullanılmalıdır.

    Args:
        user_id: Token sahibi kullanıcının unique ID'si

    Returns:
        Tuple[str, str]: (encoded_token, jti)
            - encoded_token: Base64 encoded JWT refresh token
            - jti: Token'ın unique identifier'ı (DB'de saklanmalı)

    Raises:
        JWTError: Token oluşturma sırasında encoding hatası oluşursa

    Example:
        >>> token, jti = create_refresh_token(user_id="123")
        >>> # token: eyJhbGciOiJSUzI1NiI...
        >>> # jti: "a3f2b8c9-4d5e-6f7a-8b9c-0d1e2f3a4b5c"
        >>>
        >>> # JTI'yi veritabanına kaydet
        >>> await refresh_token_repo.create(user_id=user_id, jti=jti, expires_at=...)

    Note:
        - Token type otomatik olarak "refresh" ayarlanır
        - Scopes boş liste olarak ayarlanır (refresh token'lar yetki taşımaz)
        - Default expire: 30 gün (settings.REFRESH_TOKEN_EXPIRE_DAYS)
        - JTI mutlaka DB'ye kaydedilmeli (revocation tracking için)
        - Refresh token'lar sadece yeni access token almak için kullanılır
    """
    jti = str(uuid4())
    expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "type": TokenType.REFRESH,
        "jti": jti,
        "iat": datetime.now(UTC),
        "exp": expire,
        "scopes": [],
    }
    token = jwt.encode(payload, settings.JWT_PRIVATE_KEY, algorithm="RS256")
    return token, jti


def is_token_revoked_after(iat: datetime, revoked_after: datetime | None) -> bool:
    """Token üretim zamanının kullanıcı cutoff zamanından eski olup olmadığını kontrol et."""
    if revoked_after is None:
        return False
    issued_at = iat.astimezone(UTC)
    cutoff = revoked_after.astimezone(UTC)
    return issued_at <= cutoff


def decode_token(token: str) -> TokenPayload:
    """JWT token'ı doğrular ve payload'ı parse eder.

    Verilen JWT token'ı public key ile doğrular, signature ve expiration
    kontrolü yapar. Başarılı doğrulama sonrası TokenPayload modeline
    parse edilmiş payload döndürür.

    Args:
        token: Base64 encoded JWT token string

    Returns:
        TokenPayload: Parse edilmiş token verisi
            - sub: Kullanıcı ID
            - type: Token tipi (access/refresh)
            - jti: Token unique ID
            - iat: Token oluşturma zamanı
            - exp: Token son kullanma zamanı
            - scopes: Yetki kapsamları listesi

    Raises:
        TokenExpiredError: Token süresi dolmuşsa
        InvalidTokenError: Token signature geçersiz veya format bozuksa

    Example:
        >>> payload = decode_token(access_token)
        >>> print(payload.sub)  # "123"
        >>> print(payload.type)  # TokenType.ACCESS
        >>> print(payload.scopes)  # ["read:users", "write:posts"]
        >>>
        >>> # Expired token
        >>> decode_token(old_token)  # Raises TokenExpiredError

    Note:
        - RS256 public key ile doğrulama yapılır
        - Expiration otomatik kontrol edilir (verify_exp=True)
        - Token type validation yapılmaz (access/refresh ayrımı caller'da)
        - JTI revocation kontrolü bu fonksiyonda yapılmaz (DB check gerekli)
        - Tüm datetime değerleri UTC timezone'da
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_PUBLIC_KEY,
            algorithms=["RS256"],
            options={"verify_exp": True},
        )
        return TokenPayload(**payload)
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError() from None
    except JWTError:
        raise InvalidTokenError() from None


def create_token_pair(user_id: str, scopes: list[str] | None = None) -> dict[str, str]:
    """Access ve refresh token çifti oluşturur (login response için).

    Kullanıcı girişi veya token yenileme sonrası döndürülecek token
    paketini hazırlar. OAuth2 standardına uygun format döner.

    Args:
        user_id: Token sahibi kullanıcının unique ID'si
        scopes: Access token için yetki kapsamları. Default: []

    Returns:
        Dict[str, str]: OAuth2 token response
            - access_token: Kısa ömürlü access token
            - refresh_token: Uzun ömürlü refresh token
            - token_type: "bearer" (sabit değer)

    Example:
        >>> tokens = create_token_pair(user_id="123", scopes=["read:users"])
        >>> # {
        >>> #     "access_token": "eyJhbGc...",
        >>> #     "refresh_token": "eyJhbGc...",
        >>> #     "token_type": "bearer"
        >>> # }

    Note:
        - Refresh token'ın JTI'si döndürülmez (internal kullanım için)
        - Caller refresh token JTI'sini DB'ye kaydetmeli
        - token_type her zaman "bearer" döner (OAuth2 spec)
        - Scopes yalnızca access token'a eklenir
    """
    access = create_access_token(user_id, scopes)
    refresh, _ = create_refresh_token(user_id)
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
    }
