"""FastAPI dependencies for authentication and authorization.

Domain routers protect endpoints like this::

    @router.post("/machines")
    async def create_machine(auth: Annotated[AuthContext, require(Permission.MACHINES_WRITE)]):
        ...

Every authenticated request automatically gets its database session bound to the
caller's organization, which activates row-level security on tenant tables.
"""

from typing import Annotated, Any

from fastapi import Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.client import ClientInfo, client_info
from app.core.config import Settings
from app.core.errors import CsrfFailed, NotAuthenticated, PermissionDenied
from app.db.session import bind_tenant, get_db
from app.modules.auth.service import AuthContext, resolve_session
from app.security.permissions import Permission
from app.security.rate_limit import RateLimiter
from app.security.tokens import csrf_token_matches

CSRF_HEADER = "X-CSRF-Token"
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def _rate_limiter(request: Request) -> RateLimiter:
    limiter: RateLimiter = request.app.state.rate_limiter
    return limiter


DbSession = Annotated[AsyncSession, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(_settings)]
Limiter = Annotated[RateLimiter, Depends(_rate_limiter)]
Client = Annotated[ClientInfo, Depends(client_info)]


async def _current_auth(request: Request, db: DbSession, settings: AppSettings) -> AuthContext:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise NotAuthenticated
    ctx = await resolve_session(db, settings, token)
    if ctx is None:
        raise NotAuthenticated

    if request.method not in _SAFE_METHODS and not csrf_token_matches(
        request.headers.get(CSRF_HEADER), ctx.session.id, settings.secret_key.get_secret_value()
    ):
        raise CsrfFailed

    await bind_tenant(db, ctx.organization.id)
    return ctx


CurrentAuth = Annotated[AuthContext, Depends(_current_auth)]


def require(*permissions: Permission) -> Any:
    """Dependency that authenticates and enforces every listed permission."""
    needed = frozenset(permissions)

    async def _guard(auth: CurrentAuth) -> AuthContext:
        if not needed <= auth.permissions:
            raise PermissionDenied
        return auth

    return Depends(_guard)


def set_session_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=int(settings.session_absolute_timeout.total_seconds()),
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )
