"""Integration-test harness against a real PostgreSQL.

A throwaway database is created per test session, migrated with Alembic exactly as in
production, and the app connects to it as the least-privileged runtime role, so tests
exercise the real grants and row-level-security behaviour.

Required environment (provided by `docker compose run --rm api-test` and by CI):
    TEST_ADMIN_DATABASE_URL  owner/superuser URL to any existing database
    APP_DB_USER, APP_DB_PASSWORD  the runtime role created by infra/postgres/initdb
"""

import os
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import Environment, Settings
from app.main import create_app
from tests.helpers import Browser

BACKEND_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class TestDatabase:
    admin_url: str  # owner role, connected to the test database
    app_url: str  # runtime role, connected to the test database


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.exit(f"{name} is not set; run tests via `docker compose run --rm api-test`")
    return value


@pytest.fixture(scope="session")
async def database() -> AsyncIterator[TestDatabase]:
    admin = make_url(_require_env("TEST_ADMIN_DATABASE_URL"))
    app_user, app_password = _require_env("APP_DB_USER"), _require_env("APP_DB_PASSWORD")
    name = f"georgos_test_{uuid.uuid4().hex[:8]}"

    server = create_async_engine(admin, isolation_level="AUTOCOMMIT")
    async with server.connect() as conn:
        await conn.execute(text(f'CREATE DATABASE "{name}"'))
        await conn.execute(text(f'GRANT CONNECT ON DATABASE "{name}" TO "{app_user}"'))

    admin_url = admin.set(database=name)
    app_url = admin_url.set(username=app_user, password=app_password)
    # Alembic's env.py owns its own event loop, so it runs in a separate process.
    subprocess.run(  # noqa: ASYNC221 - one-off setup before any test runs
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        env={
            **os.environ,
            "MIGRATION_DATABASE_URL": admin_url.render_as_string(hide_password=False),
            "APP_DB_USER": app_user,
        },
        check=True,
        capture_output=True,
    )
    try:
        yield TestDatabase(
            admin_url=admin_url.render_as_string(hide_password=False),
            app_url=app_url.render_as_string(hide_password=False),
        )
    finally:
        async with server.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        await server.dispose()


@pytest.fixture(scope="session")
async def admin_engine(database: TestDatabase) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(database.admin_url)
    yield engine
    await engine.dispose()


@pytest.fixture(autouse=True)
async def _clean_tables(admin_engine: AsyncEngine) -> AsyncIterator[None]:
    yield
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE organizations, users, memberships, invitations, user_sessions, "
                "audit_events, rate_limit_buckets CASCADE"
            )
        )


@pytest.fixture(scope="session")
def settings(database: TestDatabase) -> Settings:
    return Settings(
        environment=Environment.TEST,
        database_url=SecretStr(database.app_url),
        secret_key=SecretStr("test-secret-key-that-is-long-enough-0123456789"),
        session_cookie_secure=False,
        allowed_origins=["https://partner.example.com"],
    )


@pytest.fixture(scope="session")
async def app(settings: Settings) -> AsyncIterator[FastAPI]:
    application = create_app(settings, run_maintenance=False)
    async with application.router.lifespan_context(application):
        yield application


ClientFactory = Callable[..., Browser]


@pytest.fixture
def make_browser(app: FastAPI) -> ClientFactory:
    """Factory for independent browsers (separate cookie jars, configurable client IP)."""

    def _make(ip: str = "203.0.113.10") -> Browser:
        transport = httpx.ASGITransport(app=app, client=(ip, 50000))
        return Browser(httpx.AsyncClient(transport=transport, base_url="http://testserver"))

    return _make


@pytest.fixture
async def browser(make_browser: ClientFactory) -> AsyncIterator[Browser]:
    async with make_browser() as b:
        yield b
