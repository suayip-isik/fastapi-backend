"""FastAPI dependency injection tanımları."""

from app.api.dependencies.auth import (
    CurrentUserDep,
    DBDep,
    UserRepoDep,
    get_current_active_user,
    get_current_user,
    require_permissions,
)

__all__ = [
    "CurrentUserDep",
    "DBDep",
    "UserRepoDep",
    "get_current_user",
    "get_current_active_user",
    "require_permissions",
]
