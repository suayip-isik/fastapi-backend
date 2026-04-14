"""Production runtime access policy testleri."""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_production_internal_runtime_surfaces_require_access_token(client) -> None:
    """Prod'da docs/schema/metrics/health detay endpoint'leri internal token istemeli."""
    with ExitStack() as stack:
        stack.enter_context(patch("app.core.access.settings.APP_ENV", "production"))
        stack.enter_context(
            patch("app.core.access.settings.INTERNAL_ACCESS_TOKEN", "internal-secret")
        )
        stack.enter_context(patch("app.core.access.settings.DOCS_ACCESS_MODE", "internal"))
        stack.enter_context(patch("app.core.access.settings.METRICS_ACCESS_MODE", "internal"))
        stack.enter_context(patch("app.core.access.settings.HEALTH_DETAIL_ACCESS_MODE", "internal"))

        docs = await client.get("/docs")
        schema = await client.get("/schema/admin/openapi.json")
        metrics = await client.get("/metrics")
        health = await client.get("/health")
        ready = await client.get("/health/ready")
        live = await client.get("/health/live")

        authorized_docs = await client.get(
            "/docs",
            params={"access_token": "internal-secret"},
        )
        authorized_metrics = await client.get(
            "/metrics",
            headers={"X-Internal-Access-Token": "internal-secret"},
        )

    assert docs.status_code == 403
    assert schema.status_code == 403
    assert metrics.status_code == 403
    assert health.status_code == 403
    assert ready.status_code == 403
    assert live.status_code == 200
    assert authorized_docs.status_code == 200
    assert authorized_metrics.status_code == 200


@pytest.mark.asyncio
async def test_production_disabled_docs_surface_returns_404(client) -> None:
    """Disabled mode seçildiğinde docs endpoint'i bulunamadı gibi davranmalı."""
    with ExitStack() as stack:
        stack.enter_context(patch("app.core.access.settings.APP_ENV", "production"))
        stack.enter_context(patch("app.core.access.settings.DOCS_ACCESS_MODE", "disabled"))
        res = await client.get("/docs")

    assert res.status_code == 404
