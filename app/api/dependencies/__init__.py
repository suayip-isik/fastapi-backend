"""FastAPI dependency injection tanımları."""

from app.api.dependencies.auth import (
    AdminDep,
    CurrentUserDep,
    DBDep,
    UserRepoDep,
    get_current_active_user,
    get_current_user,
    require_roles,
)

__all__ = [
    "CurrentUserDep",
    "AdminDep",
    "DBDep",
    "UserRepoDep",
    "get_current_user",
    "get_current_active_user",
    "require_roles",
]
