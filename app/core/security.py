"""
Security utilities — JWT (RS256), password hashing, token management.
RS256 kullanımı: private key ile imzala, public key ile doğrula.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

import bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import InvalidTokenError, TokenExpiredError


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenPayload(BaseModel):
    sub: str           # user ID
    type: TokenType
    jti: str           # JWT ID (revocation için)
    iat: datetime
    exp: datetime
    scopes: list[str] = []


# ── Password Hashing ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """bcrypt ile password hash'le."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain.encode(), salt).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Password doğrula."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT Token ─────────────────────────────────────────────────────────────────

def create_access_token(
    user_id: str,
    scopes: list[str] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """RS256 ile imzalı access token oluştur."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": str(user_id),
        "type": TokenType.ACCESS,
        "jti": str(uuid4()),
        "iat": datetime.now(timezone.utc),
        "exp": expire,
        "scopes": scopes or [],
    }
    return jwt.encode(payload, settings.JWT_PRIVATE_KEY, algorithm="RS256")


def create_refresh_token(user_id: str) -> tuple[str, str]:
    """Refresh token oluştur. (token, jti) döner — jti DB'ye kaydedilir."""
    jti = str(uuid4())
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "type": TokenType.REFRESH,
        "jti": jti,
        "iat": datetime.now(timezone.utc),
        "exp": expire,
        "scopes": [],
    }
    token = jwt.encode(payload, settings.JWT_PRIVATE_KEY, algorithm="RS256")
    return token, jti


def decode_token(token: str) -> TokenPayload:
    """Token'ı doğrula ve payload döndür."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_PUBLIC_KEY,
            algorithms=["RS256"],
            options={"verify_exp": True},
        )
        return TokenPayload(**payload)
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError()
    except JWTError:
        raise InvalidTokenError()


def create_token_pair(user_id: str, scopes: list[str] | None = None) -> dict[str, str]:
    """Access + refresh token çifti oluştur."""
    access = create_access_token(user_id, scopes)
    refresh, _ = create_refresh_token(user_id)
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
    }
