"""Middleware unit testleri — RequestIDMiddleware, TimingMiddleware, SecurityHeadersMiddleware."""

from __future__ import annotations

import re

from httpx import AsyncClient


class TestRequestIDMiddleware:
    async def test_generates_uuid_when_no_header(self, client: AsyncClient) -> None:
        """X-Request-ID header'ı olmadan istek → UUID formatında header üretilmeli."""
        res = await client.get("/health/live")
        assert "x-request-id" in res.headers
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            res.headers["x-request-id"],
        )

    async def test_uses_existing_request_id_header(self, client: AsyncClient) -> None:
        """Gelen X-Request-ID header'ı değiştirilmeden response'a yansımalı."""
        custom_id = "my-custom-request-id-123"
        res = await client.get("/health/live", headers={"x-request-id": custom_id})
        assert res.headers["x-request-id"] == custom_id

    async def test_each_request_gets_unique_id(self, client: AsyncClient) -> None:
        """Her isteğin farklı bir request ID alması gerekir."""
        res1 = await client.get("/health/live")
        res2 = await client.get("/health/live")
        assert res1.headers["x-request-id"] != res2.headers["x-request-id"]


class TestTimingMiddleware:
    async def test_adds_process_time_header(self, client: AsyncClient) -> None:
        """Her response'da X-Process-Time-Ms header'ı bulunmalı."""
        res = await client.get("/health/live")
        assert "x-process-time-ms" in res.headers

    async def test_duration_is_non_negative_number(self, client: AsyncClient) -> None:
        """X-Process-Time-Ms değeri sıfır veya pozitif bir sayı olmalı."""
        res = await client.get("/health/live")
        duration = float(res.headers["x-process-time-ms"])
        assert duration >= 0


class TestSecurityHeadersMiddleware:
    async def test_adds_x_content_type_options(self, client: AsyncClient) -> None:
        res = await client.get("/health/live")
        assert res.headers.get("x-content-type-options") == "nosniff"

    async def test_adds_x_frame_options(self, client: AsyncClient) -> None:
        res = await client.get("/health/live")
        assert res.headers.get("x-frame-options") == "DENY"

    async def test_adds_xss_protection(self, client: AsyncClient) -> None:
        res = await client.get("/health/live")
        assert res.headers.get("x-xss-protection") == "1; mode=block"

    async def test_adds_strict_transport_security(self, client: AsyncClient) -> None:
        res = await client.get("/health/live")
        hsts = res.headers.get("strict-transport-security", "")
        assert "max-age=" in hsts

    async def test_adds_referrer_policy(self, client: AsyncClient) -> None:
        res = await client.get("/health/live")
        assert "referrer-policy" in res.headers

    async def test_adds_permissions_policy(self, client: AsyncClient) -> None:
        res = await client.get("/health/live")
        assert "permissions-policy" in res.headers

    async def test_relaxes_csp_for_docs_path(self, client: AsyncClient) -> None:
        """/docs endpoint'i için CSP daha geniş olmalı (Swagger UI inline script kullanır)."""
        res = await client.get("/docs")
        csp = res.headers.get("content-security-policy", "")
        # Swagger UI için unsafe-inline veya CDN kaynağına izin verilmeli
        assert "'unsafe-inline'" in csp or "cdn.jsdelivr.net" in csp

    async def test_relaxes_csp_for_redoc_path(self, client: AsyncClient) -> None:
        """/redoc endpoint'i için CSP daha geniş olmalı."""
        res = await client.get("/redoc")
        csp = res.headers.get("content-security-policy", "")
        assert "'unsafe-inline'" in csp or "cdn.jsdelivr.net" in csp

    async def test_strict_csp_for_api_endpoints(self, client: AsyncClient) -> None:
        """API endpoint'leri için CSP kısıtlı olmalı."""
        res = await client.get("/health/live")
        csp = res.headers.get("content-security-policy", "")
        assert "default-src 'self'" in csp
        assert "'unsafe-inline'" not in csp
