"""Cookie yardımcı fonksiyonları — auth token'ları için httpOnly cookie yönetimi."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from app.core.config import settings

if TYPE_CHECKING:
    from fastapi import Response

# Cookie isimleri
ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
) -> None:
    """Auth token'larını httpOnly cookie olarak set eder.

    Login, TOTP challenge ve refresh endpoint'lerinde kullanılır.
    Cookie'ler XSS saldırılarına karşı httpOnly olarak işaretlenir.

    Args:
        response: FastAPI Response nesnesi.
        access_token: JWT access token.
        refresh_token: JWT refresh token.

    Note:
        - httponly=True: JavaScript erişimini engeller (XSS koruması)
        - secure: HTTPS üzerinden gönderim (production'da True)
        - samesite: CSRF koruması (Lax önerilen)
        - max_age: Token TTL ile senkron
    """
    # Access token cookie - kısa ömürlü
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path=settings.COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN,
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite=_get_samesite(),
    )

    # Refresh token cookie - uzun ömürlü
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE,
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path=settings.COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN,
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite=_get_samesite(),
    )


def clear_auth_cookies(response: Response) -> None:
    """Auth cookie'lerini temizler.

    Logout endpoint'inde kullanılır. Cookie'ler max_age=0 ile silinir.

    Args:
        response: FastAPI Response nesnesi.
    """
    response.delete_cookie(
        key=ACCESS_TOKEN_COOKIE,
        path=settings.COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN,
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite=_get_samesite(),
    )

    response.delete_cookie(
        key=REFRESH_TOKEN_COOKIE,
        path=settings.COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN,
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite=_get_samesite(),
    )


def _get_samesite() -> Literal["lax", "strict", "none"]:
    """Config'den samesite değerini alır ve validate eder."""
    value = settings.COOKIE_SAMESITE.lower()
    if value in ("lax", "strict", "none"):
        return value  # type: ignore[return-value]
    return "lax"
