"""Canonical system role names and helpers."""

from __future__ import annotations

PANEL_ADMIN_ROLE = "panel_admin"
APP_USER_ROLE = "app_user"

SYSTEM_ROLE_NAMES = frozenset({PANEL_ADMIN_ROLE, APP_USER_ROLE})
