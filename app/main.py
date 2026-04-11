"""
FastAPI uygulama fabrikasi.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqladmin import Admin
from starlette.middleware.sessions import SessionMiddleware

from app.admin import get_all_views
from app.admin.auth import AdminAuthBackend
from app.admin.seed import create_default_superadmin, seed_system_roles
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.limiter import limiter
from app.core.logging import setup_logging
from app.core.middleware import (
    LanguageMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
    TimingMiddleware,
)
from app.core.redis import close_redis
from app.db.schema_guard import validate_database_schema
from app.db.session import engine


def _setup_sentry() -> None:
    """Sentry SDK'yı başlat (SENTRY_DSN tanımlıysa)."""
    dsn = settings.SENTRY_DSN.strip()
    if not dsn or not dsn.startswith("http"):
        return

    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    from sentry_sdk.types import Event as SentryEvent

    def _before_send(event: SentryEvent, hint: dict[str, object]) -> SentryEvent | None:
        """PII içeren alanları temizle."""
        request = event.get("request")
        if isinstance(request, dict):
            request.pop("cookies", None)
            request.pop("data", None)
            headers = request.get("headers")
            if isinstance(headers, dict):
                headers.pop("authorization", None)
                headers.pop("x-api-key", None)
        return event

    sentry_sdk.init(
        dsn=dsn,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        environment=settings.APP_ENV,
        release=settings.APP_VERSION,
        before_send=_before_send,
        send_default_pii=False,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Uygulama yasam dongusunu yonetir.

    Baslangicta loglama/Sentry kurulumunu yapar ve varsayilan superadmin
    kullanicisini olusturur. Kapanista DB engine ve Redis baglantisini
    guvenli sekilde kapatir.

    Args:
        app: FastAPI uygulama nesnesi.

    Yields:
        Uygulama calisirken kontrolu FastAPI'ye birakir.
    """
    setup_logging()
    _setup_sentry()
    from app.core.logging import get_logger

    logger = get_logger(__name__)
    logger.info("app_starting", version=settings.APP_VERSION, env=settings.APP_ENV)
    if settings.ENFORCE_DB_SCHEMA_CHECK:
        await validate_database_schema(engine)
    await seed_system_roles()
    await create_default_superadmin()
    yield
    await engine.dispose()
    await close_redis()
    logger.info("app_stopped")


def create_app() -> FastAPI:
    """FastAPI uygulamasini olusturur ve tum bilesenleri kaydeder.

    Middleware, exception handler, router, admin panel, metrics ve docs
    endpoint'lerini tek merkezde baglar.

    Returns:
        Konfiguru edilmis FastAPI uygulama nesnesi.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.APP_DEBUG,
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # Session Middleware (SQLAdmin icin zorunlu)
    app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

    # Rate Limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(o) for o in settings.CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time-Ms"],
    )

    # Middleware
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(LanguageMiddleware)

    # Exception Handlers
    register_exception_handlers(app)

    # Prometheus Metrics
    from app.core.metrics import setup_metrics

    setup_metrics(app)

    # Routers
    app.include_router(api_router)

    # Admin Panel
    admin = Admin(
        app,
        engine=engine,
        authentication_backend=AdminAuthBackend(secret_key=settings.SECRET_KEY),
        title=f"{settings.APP_NAME} Admin",
        base_url="/admin",
    )

    for view in get_all_views():
        admin.add_view(view)

    # Docs
    @app.get("/docs", include_in_schema=False)
    async def swagger_ui() -> HTMLResponse:
        """Swagger UI sayfasini dondurur."""
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title=f"{settings.APP_NAME} - Swagger UI",
            swagger_js_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css",
        )

    @app.get("/redoc", include_in_schema=False)
    async def redoc_ui() -> HTMLResponse:
        """ReDoc sayfasini dondurur."""
        return get_redoc_html(
            openapi_url="/openapi.json",
            title=f"{settings.APP_NAME} - ReDoc",
            redoc_js_url="https://unpkg.com/redoc@latest/bundles/redoc.standalone.js",
        )

    # Audience-specific OpenAPI schemas
    from typing import Any

    from app.api.v1.openapi import generate_audience_schema

    @app.get("/schema/admin/openapi.json", include_in_schema=False)
    async def admin_openapi() -> Any:
        """Admin audience icin filtrelenmis OpenAPI semasini dondurur."""
        return generate_audience_schema(
            app,
            audience="admin",
            title=f"{settings.APP_NAME} — Admin API",
            version=settings.APP_VERSION,
        )

    @app.get("/schema/client/openapi.json", include_in_schema=False)
    async def client_openapi() -> Any:
        """Client surface için filtrelenmiş OpenAPI şemasını döndürür."""
        return generate_audience_schema(
            app,
            audience="client",
            title=f"{settings.APP_NAME} — Client API",
            version=settings.APP_VERSION,
        )

    @app.get("/schema/admin/docs", include_in_schema=False)
    async def admin_docs() -> HTMLResponse:
        """Admin audience icin Swagger UI sayfasini dondurur."""
        return get_swagger_ui_html(
            openapi_url="/schema/admin/openapi.json",
            title=f"{settings.APP_NAME} Admin — Swagger UI",
            swagger_js_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css",
        )

    @app.get("/schema/client/docs", include_in_schema=False)
    async def client_docs() -> HTMLResponse:
        """Client surface için Swagger UI sayfasını döndürür."""
        return get_swagger_ui_html(
            openapi_url="/schema/client/openapi.json",
            title=f"{settings.APP_NAME} Client — Swagger UI",
            swagger_js_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css",
        )

    # Health Check
    @app.get("/health/live", tags=["System"], summary="Liveness probe")
    async def health_live() -> dict[str, str]:
        """Uygulama ayakta mı? (Kubernetes liveness probe)"""
        return {"status": "ok"}

    @app.get("/health/ready", tags=["System"], summary="Readiness probe")
    async def health_ready() -> dict[str, str | bool]:
        """Tüm bağımlılıklar hazır mı? (Kubernetes readiness probe)"""
        from fastapi import HTTPException

        from app.core.health import check_database, check_redis, check_storage

        db_ok, db_msg = await check_database()
        redis_ok, redis_msg = await check_redis()
        storage_ok, storage_msg = await check_storage()

        all_ok = db_ok and redis_ok and storage_ok
        body: dict[str, str | bool] = {
            "status": "ok" if all_ok else "degraded",
            "db": db_msg if db_ok else f"error: {db_msg}",
            "redis": redis_msg if redis_ok else f"error: {redis_msg}",
            "storage": storage_msg if storage_ok else f"error: {storage_msg}",
        }
        if not all_ok:
            raise HTTPException(status_code=503, detail=body)
        return body

    @app.get("/health", tags=["System"], summary="Full health check")
    async def health() -> dict[str, str | bool]:
        """Uygulama ve bağımlılık durumunu döndür."""
        from app.core.health import check_database, check_redis, check_storage

        db_ok, db_msg = await check_database()
        redis_ok, redis_msg = await check_redis()
        storage_ok, storage_msg = await check_storage()

        all_ok = db_ok and redis_ok and storage_ok
        return {
            "status": "ok" if all_ok else "degraded",
            "version": settings.APP_VERSION,
            "env": settings.APP_ENV,
            "db": db_msg if db_ok else f"error: {db_msg}",
            "redis": redis_msg if redis_ok else f"error: {redis_msg}",
            "storage": storage_msg if storage_ok else f"error: {storage_msg}",
        }

    return app


app = create_app()
