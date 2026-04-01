"""
Audience tabanlı OpenAPI şema filtreleme için yardımcı modül.

Her router, `tag_router()` helper'ı ile audience metadata'sı alır.
Bu metadata, generate_audience_schema() tarafından filtreleme sırasında kullanılır.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from fastapi.routing import APIRoute

Audience = Literal["admin", "user", "mobile"]

ADMIN: list[Audience] = ["admin"]
USER: list[Audience] = ["user"]
MOBILE: list[Audience] = ["mobile"]
USER_AND_MOBILE: list[Audience] = ["user", "mobile"]
ALL: list[Audience] = ["admin", "user", "mobile"]


def tag_router(router: APIRouter, audiences: list[Audience]) -> APIRouter:
    """
    Router'daki her APIRoute'a x-audiences ekler.
    Per-route openapi_extra override'larını korur (setdefault kullanır).
    tag_router() çağrısından önce route decorator'ında tanımlanan x-audiences değerleri korunur.
    """
    for route in router.routes:
        if isinstance(route, APIRoute):
            extra = route.openapi_extra or {}
            extra.setdefault("x-audiences", audiences)
            route.openapi_extra = extra
    return router
