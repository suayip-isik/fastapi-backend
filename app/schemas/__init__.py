"""Pydantic request/response şemaları."""

from app.schemas.auth import (
    LoginRequest,
    OAuthCallbackRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.user import UpdateUserRequest, UserResponse

__all__ = [
    "RegisterRequest",
    "LoginRequest",
    "TokenResponse",
    "RefreshRequest",
    "OAuthCallbackRequest",
    "UserResponse",
    "UpdateUserRequest",
    "PaginatedResponse",
    "MessageResponse",
]
