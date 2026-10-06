"""Application factory.

``create_app`` takes its settings explicitly so tests can build isolated instances;
``build_app`` reads them from the environment and is what uvicorn serves.
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Environment, Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import (
    OriginGuardMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from app.db.session import create_engine, create_session_factory
from app.maintenance import report_crash, run_forever
from app.modules.auth.dependencies import CSRF_HEADER
from app.modules.auth.router import router as auth_router
from app.modules.health.router import router as health_router
from app.modules.organizations.router import invitations_router
from app.modules.organizations.router import router as organizations_router
from app.security.rate_limit import RateLimiter

API_PREFIX = "/api"


def create_app(settings: Settings, *, run_maintenance: bool = True) -> FastAPI:
    configure_logging(settings.log_level, json_output=not settings.is_development)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings)
        session_factory = create_session_factory(engine)
        app.state.settings = settings
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.rate_limiter = RateLimiter(session_factory)
        maintenance = None
        if run_maintenance:
            maintenance = asyncio.create_task(run_forever(session_factory))
            maintenance.add_done_callback(report_crash)
        try:
            yield
        finally:
            if maintenance is not None:
                maintenance.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await maintenance
            await engine.dispose()

    docs_enabled = settings.environment is Environment.DEVELOPMENT
    app = FastAPI(
        title="Georgos Map API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=f"{API_PREFIX}/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json" if docs_enabled else None,
    )

    register_error_handlers(app)

    # Starlette runs the last-added middleware first: request context wraps everything.
    if settings.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=["Content-Type", CSRF_HEADER],
            max_age=600,
        )
    app.add_middleware(OriginGuardMiddleware, allowed_origins=settings.allowed_origins)
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.session_cookie_secure)
    app.add_middleware(RequestContextMiddleware)

    v1 = APIRouter(prefix=f"{API_PREFIX}/v1")
    v1.include_router(auth_router)
    v1.include_router(organizations_router)
    v1.include_router(invitations_router)
    app.include_router(v1)
    app.include_router(health_router, prefix=API_PREFIX)

    return app


def build_app() -> FastAPI:
    """Entry point for uvicorn: ``uvicorn --factory app.main:build_app``."""
    return create_app(get_settings())
