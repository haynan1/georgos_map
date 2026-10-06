"""Cross-cutting guarantees: health, headers, error envelope, configuration safety."""

import pytest
from pydantic import ValidationError

from app.core.config import Environment, Settings
from tests.helpers import Browser


async def test_health_endpoints(browser: Browser) -> None:
    live = await browser.http.get("/api/health/live")
    ready = await browser.http.get("/api/health/ready")
    assert live.status_code == 200
    assert ready.json() == {"status": "ok", "database": "ok"}


async def test_security_headers_and_request_id(browser: Browser) -> None:
    response = await browser.http.get("/api/health/live", headers={"X-Request-ID": "abc12345"})
    headers = response.headers
    assert headers["X-Request-ID"] == "abc12345"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Cache-Control"] == "no-store"
    assert "default-src 'none'" in headers["Content-Security-Policy"]
    assert "server" not in {name.lower() for name in headers}


async def test_untrusted_request_id_is_replaced(browser: Browser) -> None:
    response = await browser.http.get("/api/health/live", headers={"X-Request-ID": "<script>"})
    assert response.headers["X-Request-ID"] != "<script>"


async def test_errors_share_one_envelope(browser: Browser) -> None:
    response = await browser.http.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert error["request_id"] == response.headers["X-Request-ID"]


async def test_docs_are_disabled_outside_development(browser: Browser) -> None:
    assert (await browser.http.get("/api/docs")).status_code == 404
    assert (await browser.http.get("/api/openapi.json")).status_code == 404


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": Environment.PRODUCTION,
        "database_url": "postgresql+asyncpg://u:p@localhost/db",
        "secret_key": "a" * 64,
        "session_cookie_secure": True,
    }
    return Settings(**(values | overrides))  # type: ignore[arg-type]


def test_production_rejects_placeholder_secret() -> None:
    with pytest.raises(ValidationError, match="placeholder"):
        _settings(secret_key="change-me-generate-a-64-char-hex-secret-here-please-000000")


def test_production_requires_secure_cookies() -> None:
    with pytest.raises(ValidationError, match="SESSION_COOKIE_SECURE"):
        _settings(session_cookie_secure=False)


def test_wildcard_origin_is_rejected() -> None:
    with pytest.raises(ValidationError, match="wildcard"):
        _settings(allowed_origins="*")


def test_origins_are_parsed_from_csv() -> None:
    settings = _settings(allowed_origins="https://a.example, https://b.example/")
    assert settings.allowed_origins == ["https://a.example", "https://b.example"]


def test_secure_cookie_uses_host_prefix() -> None:
    assert _settings().session_cookie_name == "__Host-georgos_session"
