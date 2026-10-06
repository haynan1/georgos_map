"""HTTP middleware, written as pure ASGI.

Starlette's ``BaseHTTPMiddleware`` wraps every request in an extra task and buffers
streaming semantics; plain ASGI middleware has none of that overhead.
"""

import logging
import re
import time
import uuid
from collections.abc import Iterable
from urllib.parse import urlsplit

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.request_context import bind_request_id, reset_request_id

access_logger = logging.getLogger("georgos.access")

_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class RequestContextMiddleware:
    """Assigns a request id, exposes it in ``X-Request-ID`` and writes one access log line.

    The query string is deliberately never logged: it is the most common place for
    secrets to leak into log storage.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get("x-request-id", "")
        request_id = incoming if _SAFE_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        token = bind_request_id(request_id)
        started = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            access_logger.info(
                "request",
                extra={
                    "method": scope["method"],
                    "path": scope["path"],
                    "status": status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
            reset_request_id(token)


class SecurityHeadersMiddleware:
    """Applies a locked-down header set to every API response.

    The API only ever returns JSON, so the CSP forbids everything. Interactive docs (only
    mounted in development) need scripts and styles from the docs CDN, so they get a
    relaxed policy scoped to those paths.
    """

    _BASE: tuple[tuple[str, str], ...] = (
        ("X-Content-Type-Options", "nosniff"),
        ("X-Frame-Options", "DENY"),
        ("Referrer-Policy", "no-referrer"),
        ("Cross-Origin-Opener-Policy", "same-origin"),
        ("Cross-Origin-Resource-Policy", "same-origin"),
        ("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()"),
    )
    _API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    _DOCS_CSP = (
        "default-src 'self'; img-src 'self' data: https://fastapi.tiangolo.com; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; frame-ancestors 'none'"
    )
    _DOCS_PATHS = ("/api/docs", "/api/openapi.json")

    def __init__(self, app: ASGIApp, *, hsts: bool) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        is_docs = scope["path"].startswith(self._DOCS_PATHS)

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in self._BASE:
                    headers[name] = value
                headers["Content-Security-Policy"] = self._DOCS_CSP if is_docs else self._API_CSP
                # Every API response is user-specific; no intermediary may store it.
                headers["Cache-Control"] = "no-store"
                if self.hsts:
                    headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
            await send(message)

        await self.app(scope, receive, send_wrapper)


class OriginGuardMiddleware:
    """Rejects state-changing requests that a browser marks as cross-site.

    Defense in depth on top of SameSite cookies and the per-session CSRF token: it also
    protects unauthenticated endpoints (login, registration) against login-CSRF.
    Requests without ``Origin``/``Sec-Fetch-Site`` (curl, server-to-server) pass, because
    they cannot carry a victim's browser cookies.
    """

    def __init__(self, app: ASGIApp, *, allowed_origins: Iterable[str]) -> None:
        self.app = app
        self.allowed = frozenset(allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in _UNSAFE_METHODS:
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        if self._is_cross_site(headers):
            response = JSONResponse(
                {"error": {"code": "origin_rejected", "message": "Origem não permitida."}},
                status_code=403,
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)

    def _is_cross_site(self, headers: Headers) -> bool:
        origin = headers.get("origin")
        if origin is not None:
            if origin in self.allowed:
                return False
            return urlsplit(origin).netloc != headers.get("host", "")
        return headers.get("sec-fetch-site") == "cross-site"
