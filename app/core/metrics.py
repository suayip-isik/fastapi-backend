"""
Prometheus metrics modülü.
prometheus-fastapi-instrumentator ile HTTP metriklerini toplar,
custom gauge/counter'lar ile uygulama metriklerini izler.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from prometheus_client import Counter, Gauge
from prometheus_fastapi_instrumentator import Instrumentator

if TYPE_CHECKING:
    from fastapi import FastAPI

# ── Custom Metrics ────────────────────────────────────────────────────────────

active_websocket_connections = Gauge(
    "websocket_active_connections",
    "Aktif WebSocket bağlantısı sayısı",
    labelnames=["room_id"],
)

upload_bytes_total = Counter(
    "upload_bytes_total",
    "Toplam yüklenen byte miktarı",
    labelnames=["user_id"],
)

arq_jobs_enqueued_total = Counter(
    "arq_jobs_enqueued_total",
    "ARQ kuyruğuna eklenen toplam iş sayısı",
    labelnames=["task_name"],
)

# ── Instrumentator ────────────────────────────────────────────────────────────

_instrumentator: Instrumentator | None = None


def setup_metrics(app: FastAPI) -> None:
    """
    Prometheus metriklerini FastAPI uygulamasına bağla.
    /metrics endpoint'ini oluşturur.
    """
    global _instrumentator
    _instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=False,
        excluded_handlers=["/metrics", "/health", "/health/live", "/health/ready"],
        body_handlers=[],
    )
    _instrumentator.instrument(app)
    _instrumentator.expose(app, endpoint="/metrics", tags=["System"], include_in_schema=False)
