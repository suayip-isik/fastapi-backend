"""Auth şemaları — request/response modelleri."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator


def validate_password_strength(v: str) -> str:
    """Şifrenin karmaşıklık kurallarını karşılayıp karşılamadığını doğrular.

    Şifrenin en az bir büyük harf, bir küçük harf ve bir rakam içerdiğini
    kontrol eder. Eksik kriterler toplu olarak raporlanır.

    Args:
        v: Doğrulanacak düz metin şifre.

    Returns:
        Doğrulamayı geçen orijinal şifre değeri.

    Raises:
        ValueError: Şifre büyük harf, küçük harf veya rakam kriterlerinden
            birini ya da birkaçını karşılamıyorsa. Hata mesajı eksik kriterleri
            virgülle ayrılmış biçimde listeler.

    Note:
        - Bu fonksiyon doğrudan çağrılabileceği gibi Pydantic field_validator
          içinden de kullanılır (RegisterRequest, ResetPasswordRequest).
        - Uzunluk kontrolü Field(min_length=8) ile ayrıca yapılır.

    Example:
        >>> validate_password_strength("SecurePass1")
        'SecurePass1'
        >>> validate_password_strength("weakpass")
        # ValueError: Şifre şunları içermeli: büyük harf, rakam
    """
    errors = []
    if not any(c.isupper() for c in v):
        errors.append("büyük harf")
    if not any(c.islower() for c in v):
        errors.append("küçük harf")
    if not any(c.isdigit() for c in v):
        errors.append("rakam")
    if errors:
        raise ValueError(f"Şifre şunları içermeli: {', '.join(errors)}")
    return v


class RegisterRequest(BaseModel):
    """Kullanıcı kaydı için request schema.

    Email/password ile yeni kullanıcı kaydı yapar. Email benzersiz olmalı,
    şifre en az 8 karakter, büyük harf, küçük harf ve rakam içermelidir.

    Attributes:
        email: Kullanıcı email adresi (EmailStr validation ile format kontrolü)
        password: Kullanıcı şifresi (min 8, max 128 karakter, complexity validation)
        full_name: Opsiyonel kullanıcı tam adı (max 255 karakter)

    Example:
        >>> request = RegisterRequest(
        ...     email="user@example.com",
        ...     password="SecurePass123",
        ...     full_name="John Doe"
        ... )
    """

    email: EmailStr = Field(..., max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)

    @field_validator("password")
    @classmethod
    def _validate_password(cls, v: str) -> str:
        """Şifre alanını karmaşıklık kurallarına göre doğrular.

        validate_password_strength fonksiyonuna delege eder. Büyük harf,
        küçük harf ve rakam zorunluluğunu kontrol eder.

        Args:
            v: Doğrulanacak ham şifre değeri.

        Returns:
            Doğrulamayı geçen şifre değeri.

        Raises:
            ValueError: Şifre karmaşıklık kriterlerini karşılamıyorsa.
        """
        return validate_password_strength(v)


class LoginRequest(BaseModel):
    """Kullanıcı girişi için request schema.

    Email/password ile kimlik doğrulamanın birinci adımı. TOTP aktif
    hesaplar için yanıt partial_token içerir; ikinci adım için
    /auth/totp-challenge kullanılır.

    Attributes:
        email: Kullanıcı email adresi
        password: Kullanıcı şifresi (plain text, backend'de bcrypt ile doğrulanır)
    """

    email: EmailStr
    password: str


class PartialAuthResponse(BaseModel):
    """TOTP doğrulaması gereken login yanıtı.

    Login adım 1'de kullanıcının TOTP'u aktifse döner.
    partial_token ile /auth/totp-challenge'a istek yapılmalıdır.

    Attributes:
        requires_totp: Her zaman True — TOTP adımının gerekli olduğunu belirtir
        partial_token: İkinci adım için kısa ömürlü (5 dk) opaque token
    """

    requires_totp: bool = True
    partial_token: str


class TOTPChallengeRequest(BaseModel):
    """TOTP challenge için request schema.

    Login adım 2. partial_token ile authenticator uygulamasından alınan
    kod (veya backup kodu) birlikte gönderilir.

    Attributes:
        partial_token: /auth/login'den alınan partial token
        code: 6 haneli TOTP kodu veya 8 karakterli backup kodu
    """

    partial_token: str
    code: str = Field(
        ...,
        min_length=6,
        max_length=8,
        description="6 haneli TOTP kodu veya 8 karakterli backup kodu",
    )


class TokenResponse(BaseModel):
    """JWT token çifti için response schema.

    Login ve token refresh işlemlerinden döner. Access token kısa ömürlü
    (30 dakika), refresh token uzun ömürlü (30 gün).

    Attributes:
        access_token: RS256 JWT access token (30 dakika geçerli)
        refresh_token: RS256 JWT refresh token (30 gün geçerli)
        token_type: OAuth2 token tipi (her zaman "bearer")

    Example:
        >>> response = TokenResponse(
        ...     access_token="eyJhbGc...",
        ...     refresh_token="eyJhbGc..."
        ... )
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Access token yenileme için request schema.

    Süresi dolmuş access token'ı yenilemek için kullanılır.
    Refresh token doğrulanıp yeni token çifti döner.

    Attributes:
        refresh_token: Geçerli refresh token (RS256 JWT)

    Example:
        >>> request = RefreshRequest(refresh_token="eyJhbGc...")
    """

    refresh_token: str


class OAuthCallbackRequest(BaseModel):
    """OAuth2 callback işlemi için request schema.

    Google/GitHub OAuth flow'undan gelen authorization code'u işler.
    State parametresi CSRF koruması için kullanılır.

    Attributes:
        code: OAuth2 authorization code (provider'dan gelen)
        state: CSRF koruması için state parametresi (opsiyonel)

    Example:
        >>> request = OAuthCallbackRequest(
        ...     code="4/0AX4XfWh...",
        ...     state="random-state-string"
        ... )
    """

    code: str
    state: str | None = None


class VerifyEmailRequest(BaseModel):
    """Email doğrulama için request schema.

    Kayıt sonrası email'e gönderilen doğrulama token'ını işler.
    Token geçerliyse kullanıcının is_verified flag'i true olur.

    Attributes:
        token: Email doğrulama token'ı (JWT veya UUID)

    Example:
        >>> request = VerifyEmailRequest(token="eyJhbGc...")
    """

    token: str


class ResendVerificationRequest(BaseModel):
    """Email doğrulama token'ını yeniden gönderme request schema.

    Doğrulama email'i almayan veya token'ı kaybeden kullanıcılar için.
    Email adresine yeni doğrulama linki gönderilir.

    Attributes:
        email: Doğrulama email'i gönderilecek kullanıcı email adresi

    Example:
        >>> request = ResendVerificationRequest(email="user@example.com")
    """

    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    """Şifre sıfırlama başlatma için request schema.

    Şifresini unutan kullanıcılar için. Email adresine şifre sıfırlama
    linki gönderilir.

    Attributes:
        email: Şifre sıfırlama linki gönderilecek kullanıcı email adresi

    Example:
        >>> request = ForgotPasswordRequest(email="user@example.com")
    """

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Şifre sıfırlama işlemi için request schema.

    Email'den gelen şifre sıfırlama token'ı ile yeni şifre belirlenir.
    Token geçerliyse şifre bcrypt ile hash'lenip kaydedilir.

    Attributes:
        token: Şifre sıfırlama token'ı (email'den gelen)
        new_password: Yeni şifre (min 8, max 128 karakter, complexity validation)

    Example:
        >>> request = ResetPasswordRequest(
        ...     token="eyJhbGc...",
        ...     new_password="NewSecurePass123"
        ... )
    """

    token: str = Field(..., min_length=10)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _validate_password(cls, v: str) -> str:
        """Yardımcı fonksiyon."""
        return validate_password_strength(v)


class LogoutRequest(BaseModel):
    """Kullanıcı çıkışı için request schema.

    Kullanıcı oturumunu sonlandırır. Refresh token verilirse token
    revoke edilir (blacklist'e alınır).

    Attributes:
        refresh_token: Revoke edilecek refresh token (opsiyonel)

    Example:
        >>> # Token ile logout
        >>> request = LogoutRequest(refresh_token="eyJhbGc...")
        >>> # Token olmadan logout
        >>> request = LogoutRequest()
    """

    refresh_token: str | None = None
