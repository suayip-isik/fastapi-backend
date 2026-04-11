"""Surface tabanlı OpenAPI şema filtreleme için yardımcı modül."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from fastapi.routing import APIRoute

if TYPE_CHECKING:
    from fastapi import APIRouter

SchemaTarget = Literal["admin", "client"]
Surface = Literal["admin", "client", "shared"]

ADMIN: list[Surface] = ["admin"]
CLIENT: list[Surface] = ["client"]
SHARED: list[Surface] = ["shared"]
ADMIN_AND_SHARED: list[Surface] = ["admin", "shared"]
CLIENT_AND_SHARED: list[Surface] = ["client", "shared"]
ALL: list[Surface] = ["admin", "client", "shared"]


def tag_router(router: APIRouter, surfaces: list[Surface]) -> APIRouter:
    """
    Router'daki her APIRoute'a x-surfaces ekler.
    Per-route openapi_extra override'larını korur.
    """
    for route in router.routes:
        if isinstance(route, APIRoute):
            extra = route.openapi_extra or {}
            extra.setdefault("x-surfaces", surfaces)
            route.openapi_extra = extra
    return router
