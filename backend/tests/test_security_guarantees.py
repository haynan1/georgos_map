"""System-wide security guarantees.

The route-enumeration tests cover every endpoint registered now *and in the future*: a new
endpoint that forgets authentication or CSRF protection fails CI without anyone having to
remember to write a test for it.
"""

import re
import uuid
from datetime import timedelta

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.responses import Response

from app.core.config import Environment, Settings
from app.main import create_app
from app.modules.auth.dependencies import clear_session_cookie, set_session_cookie
from app.modules.auth.service import utcnow
from tests.conftest import ClientFactory
from tests.helpers import API, PASSWORD, Browser

# Endpoints that are intentionally reachable without a session.
PUBLIC = {
    ("POST", f"{API}/auth/register"),
    ("POST", f"{API}/auth/login"),
    ("POST", f"{API}/invitations/preview"),
    ("POST", f"{API}/invitations/accept"),
}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _api_routes(app: FastAPI) -> list[tuple[str, str]]:
    """Every (METHOD, path) under the versioned API, read from the app's own OpenAPI
    schema (the public, stable view of the routing table). Path ids become random UUIDs."""
    routes: list[tuple[str, str]] = []
    for path, operations in app.openapi()["paths"].items():
        if path.startswith(API):
            concrete = re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path)
            routes.extend((method.upper(), concrete) for method in operations)
    return sorted(routes)


async def test_every_non_public_endpoint_requires_a_session(app: FastAPI, browser: Browser) -> None:
    protected = [route for route in _api_routes(app) if route not in PUBLIC]
    assert len(protected) >= 15  # sanity: the enumeration really found the API

    for method, path in protected:
        response = await browser.http.request(method, path, json={})
        assert response.status_code == 401, f"{method} {path} is reachable without a session"
        assert response.json()["error"]["code"] == "not_authenticated"


async def test_every_state_changing_endpoint_requires_csrf(app: FastAPI, browser: Browser) -> None:
    await browser.register()
    unsafe = [
        (method, path)
        for method, path in _api_routes(app)
        if method not in SAFE_METHODS and (method, path) not in PUBLIC
    ]
    assert len(unsafe) >= 10

    for method, path in unsafe:
        response = await browser.http.request(method, path, json={})
        assert response.status_code == 403, f"{method} {path} accepts requests without CSRF"
        assert response.json()["error"]["code"] == "csrf_failed"


async def test_forged_session_cookie_is_rejected(browser: Browser) -> None:
    browser.http.cookies.set("georgos_session", "x" * 43)
    assert (await browser.get("/auth/session")).status_code == 401


async def test_viewer_cannot_reach_management_endpoints(make_browser: ClientFactory) -> None:
    async with make_browser() as owner, make_browser() as viewer:
        await owner.register()
        await viewer.accept(await owner.invite("leitor@fazenda.com.br", "viewer"), name="Leitor")

        assert (await viewer.get("/organization/invitations")).status_code == 403
        assert (await viewer.get("/organization/audit-events")).status_code == 403
        some_id = uuid.uuid4()
        assert (await viewer.delete(f"/organization/invitations/{some_id}")).status_code == 403
        assert (await viewer.delete(f"/organization/members/{some_id}")).status_code == 403


# --- Session lifetime ---------------------------------------------------------------


async def test_idle_session_expires(browser: Browser, admin_engine: AsyncEngine) -> None:
    await browser.register()
    async with admin_engine.begin() as conn:
        await conn.execute(
            text("UPDATE user_sessions SET last_seen_at = :at"),
            {"at": utcnow() - timedelta(hours=25)},
        )
    assert (await browser.get("/auth/session")).status_code == 401


async def test_session_has_an_absolute_lifetime(
    browser: Browser, admin_engine: AsyncEngine
) -> None:
    await browser.register()
    async with admin_engine.begin() as conn:
        await conn.execute(
            text("UPDATE user_sessions SET expires_at = :at"), {"at": utcnow() - timedelta(1)}
        )
    assert (await browser.get("/auth/session")).status_code == 401


async def test_deactivated_user_loses_access(
    make_browser: ClientFactory, admin_engine: AsyncEngine
) -> None:
    async with make_browser() as browser:
        await browser.register()
        async with admin_engine.begin() as conn:
            await conn.execute(text("UPDATE users SET is_active = false"))

        assert (await browser.get("/auth/session")).status_code == 401
    async with make_browser() as fresh:
        assert (await fresh.login("ana@fazenda.com.br")).status_code == 401


def test_secure_session_cookie_attributes() -> None:
    settings = Settings(
        environment=Environment.PRODUCTION,
        database_url=SecretStr("postgresql+asyncpg://u:p@localhost/db"),
        secret_key=SecretStr("a" * 64),
        session_cookie_secure=True,
    )
    response = Response()
    set_session_cookie(response, settings, "token-value")
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("__Host-georgos_session=token-value;")
    for attribute in ("HttpOnly", "Secure", "Path=/", "SameSite=lax", "Max-Age=1209600"):
        assert attribute in cookie

    cleared = Response()
    clear_session_cookie(cleared, settings)
    assert "Max-Age=0" in cleared.headers["set-cookie"]


async def test_logout_tells_the_browser_to_drop_the_cookie(browser: Browser) -> None:
    await browser.register()
    response = await browser.http.post(
        f"{API}/auth/logout", headers={"X-CSRF-Token": browser.csrf or ""}
    )
    assert response.status_code == 204
    assert "Max-Age=0" in response.headers["set-cookie"]


# --- Invitations and audit -------------------------------------------------------------


async def test_expired_invitation_is_unusable(
    make_browser: ClientFactory, admin_engine: AsyncEngine
) -> None:
    async with make_browser() as owner, make_browser() as guest:
        await owner.register()
        token = await owner.invite("carlos@fazenda.com.br", "viewer")
        async with admin_engine.begin() as conn:
            await conn.execute(
                text("UPDATE invitations SET expires_at = :at"), {"at": utcnow() - timedelta(1)}
            )
        assert (await guest.post("/invitations/preview", {"token": token})).status_code == 410
        assert (await guest.accept(token)).status_code == 410


async def test_admin_cannot_cancel_an_owner_invitation(make_browser: ClientFactory) -> None:
    async with make_browser() as owner, make_browser() as admin:
        await owner.register()
        await admin.accept(await owner.invite("admin@fazenda.com.br", "admin"), name="Admin")
        await owner.invite("socio@fazenda.com.br", "owner")
        invitation = next(
            i for i in (await owner.get("/organization/invitations")).json() if i["role"] == "owner"
        )
        response = await admin.delete(f"/organization/invitations/{invitation['id']}")
        assert response.status_code == 403


async def test_audit_trail_is_isolated_per_organization(make_browser: ClientFactory) -> None:
    async with make_browser() as ana, make_browser() as bruno:
        await ana.register()
        await ana.patch("/organization", {"name": "Fazenda Renomeada"})
        await bruno.register("bruno@sitio.com.br", organization="Sítio Esperança", name="Bruno")

        events = (await bruno.get("/organization/audit-events")).json()
        assert [e["action"] for e in events] == ["organization.created"]
        assert {e["actor_name"] for e in events} == {"Bruno"}


async def test_registration_is_rate_limited_per_ip(make_browser: ClientFactory) -> None:
    statuses = []
    for i in range(6):
        async with make_browser(ip="192.0.2.99") as browser:
            response = await browser.post(
                "/auth/register",
                {
                    "organization_name": f"Fazenda {i}",
                    "full_name": "Pessoa Teste",
                    "email": f"pessoa{i}@fazenda.com.br",
                    "password": PASSWORD,
                },
            )
            statuses.append(response.status_code)
    assert statuses == [201] * 5 + [429]


async def test_whitespace_only_password_is_rejected(browser: Browser) -> None:
    response = await browser.post(
        "/auth/register",
        {
            "organization_name": "Fazenda",
            "full_name": "Ana",
            "email": "ana@fazenda.com.br",
            "password": " " * 16,
        },
    )
    assert response.status_code == 422


# --- Failure paths ---------------------------------------------------------------------


async def test_readiness_reports_unavailable_database(settings: Settings) -> None:
    broken = settings.model_copy(
        update={"database_url": SecretStr("postgresql+asyncpg://nobody:x@127.0.0.1:1/none")}
    )
    app = create_app(broken, run_maintenance=False)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as http:
            response = await http.get("/api/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
async def test_unhandled_errors_do_not_leak_details(settings: Settings) -> None:
    app = create_app(settings, run_maintenance=False)

    async def explode() -> None:
        raise RuntimeError("internal detail: secret table name")

    app.add_api_route("/api/explode", explode)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as http:
            response = await http.get("/api/explode")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "secret table" not in response.text
