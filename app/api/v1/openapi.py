"""
Audience-specific OpenAPI şema üretici.

Her audience (admin, user, mobile) için yalnızca ilgili endpoint'leri içeren
filtrelenmiş bir OpenAPI şeması üretir.
"""

from __future__ import annotations

import copy
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.api.v1.audiences import ALL, Audience

_schema_cache: dict[str, dict[str, Any]] = {}

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}


def _collect_refs(obj: Any, refs: set[str]) -> None:
    """Bir dict/list yapısı içindeki tüm $ref değerlerini recursive olarak toplar."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "$ref" and isinstance(value, str):
                refs.add(value)
            else:
                _collect_refs(value, refs)
    elif isinstance(obj, list):
        for item in obj:
            _collect_refs(item, refs)


def _extract_schema_name(ref: str) -> str | None:
    """'#/components/schemas/Foo' → 'Foo'"""
    prefix = "#/components/schemas/"
    if ref.startswith(prefix):
        return ref[len(prefix) :]
    return None


def _collect_all_schema_refs(
    components: dict[str, Any],
    needed: set[str],
) -> set[str]:
    """
    Verilen schema isimlerinden başlayarak, components/schemas içindeki
    tüm bağımlı schema isimlerini recursive olarak toplar.
    """
    all_needed: set[str] = set()
    queue = list(needed)
    while queue:
        name = queue.pop()
        if name in all_needed:
            continue
        all_needed.add(name)
        schema_def = components.get(name, {})
        sub_refs: set[str] = set()
        _collect_refs(schema_def, sub_refs)
        for ref in sub_refs:
            child = _extract_schema_name(ref)
            if child and child not in all_needed:
                queue.append(child)
    return all_needed


def _build_schema(
    app: FastAPI,
    audience: Audience,
    title: str,
    version: str,
) -> dict[str, Any]:
    schema = copy.deepcopy(
        get_openapi(
            title=title,
            version=version,
            routes=app.routes,
        )
    )

    # Paths filtrele
    paths_to_delete: list[str] = []
    for path, path_item in schema.get("paths", {}).items():
        methods_to_delete: list[str] = []
        for method, operation in path_item.items():
            if method not in HTTP_METHODS:
                continue
            if not isinstance(operation, dict):
                continue
            # x-audiences tanımlı değilse ALL kabul et (health gibi inline route'lar)
            audiences_for_op: list[str] = operation.get("x-audiences", ALL)
            if audience not in audiences_for_op:
                methods_to_delete.append(method)

        for method in methods_to_delete:
            del path_item[method]

        # Path'te hiç HTTP method kalmadıysa path'i de sil
        has_methods = any(m in path_item for m in HTTP_METHODS)
        if not has_methods:
            paths_to_delete.append(path)

    for path in paths_to_delete:
        del schema["paths"][path]

    # Kalan operation'lardan kullanılan $ref'leri topla
    used_refs: set[str] = set()
    _collect_refs(schema.get("paths", {}), used_refs)

    # components/schemas'ı kullanılmayan model'lerden temizle
    components = schema.get("components", {}).get("schemas", {})
    if components:
        directly_needed = {
            name for ref in used_refs if (name := _extract_schema_name(ref)) is not None
        }
        all_needed = _collect_all_schema_refs(components, directly_needed)

        for name in list(components.keys()):
            if name not in all_needed:
                del components[name]

    # x-audiences key'ini output'tan temizle (SDK generator'lar için gereksiz)
    for path_item in schema.get("paths", {}).values():
        for method, operation in path_item.items():
            if method in HTTP_METHODS and isinstance(operation, dict):
                operation.pop("x-audiences", None)

    return schema


def generate_audience_schema(
    app: FastAPI,
    audience: Audience,
    title: str,
    version: str,
) -> dict[str, Any]:
    """
    Verilen audience için filtrelenmiş OpenAPI şeması döndürür.
    Production'da (APP_DEBUG=False) sonuç cache'lenir.
    """
    from app.core.config import settings

    if not settings.APP_DEBUG and audience in _schema_cache:
        return _schema_cache[audience]

    schema = _build_schema(app, audience, title, version)

    if not settings.APP_DEBUG:
        _schema_cache[audience] = schema

    return schema
