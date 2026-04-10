"""API surface tanımları."""

from enum import StrEnum


class Surface(StrEnum):
    """API yüzeyleri."""

    CLIENT = "client"
    ADMIN = "admin"
    SHARED = "shared"
