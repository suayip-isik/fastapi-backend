"""
FastAPI uygulama fabrikasi.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import HTMLResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqladmin import Admin
from starlette.middleware.sessions import SessionMiddleware

from app.admin.auth import AdminAuthBackend
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import (
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
    TimingMiddleware,
)
from app.db.session import engine
from app.admin import get_all_views
from app.admin.seed import create_default_admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    from app.core.logging import get_logger

    logger = get_logger(__name__)
    logger.info("app_starting", version=settings.APP_VERSION, env=settings.APP_ENV)
    await create_default_admin()
    yield
    await engine.dispose()
    logger.info("app_stopped")


def create_app() -> FastAPI:
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
    limiter = Limiter(
        key_func=get_remote_address,
        storage_uri=settings.REDIS_URL,
        default_limits=[settings.RATE_LIMIT_DEFAULT],
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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

    # Exception Handlers
    register_exception_handlers(app)

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
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title=f"{settings.APP_NAME} - Swagger UI",
            swagger_js_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css",
        )

    @app.get("/redoc", include_in_schema=False)
    async def redoc_ui() -> HTMLResponse:
        return get_redoc_html(
            openapi_url="/openapi.json",
            title=f"{settings.APP_NAME} - ReDoc",
            redoc_js_url="https://unpkg.com/redoc@latest/bundles/redoc.standalone.js",
        )

    # Health Check
    @app.get("/health", tags=["System"])
    async def health():
        return {"status": "ok", "version": settings.APP_VERSION, "env": settings.APP_ENV}

    return app


app = create_app()
