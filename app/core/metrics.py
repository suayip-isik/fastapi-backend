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
    """Prometheus metrics instrumentator'ı FastAPI uygulamasına ekler.

    /metrics endpoint'ini otomatik oluşturur ve HTTP metriklerini toplamaya başlar.
    Request count, latency, response status code gibi standart metrikleri toplar.
    Health check endpoint'leri metriklerden hariç tutulur.

    Args:
        app: FastAPI application instance

    Note:
        - /metrics endpoint otomatik expose edilir (Swagger'da görünmez)
        - Grafana/Prometheus ile kullanılabilir
        - Metrikler: http_requests_total, http_request_duration_seconds vb.
        - Health endpoint'leri (/health, /health/live, /health/ready) hariç tutulur
        - Status kodları gruplandırılır (2xx, 3xx, 4xx, 5xx)

    Example:
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>> setup_metrics(app)
        >>> # GET /metrics -> Prometheus format metrikleri döner
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
