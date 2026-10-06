import uuid

from fastapi import APIRouter, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import NotAuthenticated
from app.db.session import bind_tenant
from app.modules.audit.service import AuditAction, record
from app.modules.auth import service
from app.modules.auth.dependencies import (
    AppSettings,
    Client,
    CurrentAuth,
    DbSession,
    Limiter,
    clear_session_cookie,
    set_session_cookie,
)
from app.modules.auth.schemas import (
    ActiveSessionView,
    ChangePasswordRequest,
    LoginRequest,
    OrganizationChoice,
    OrganizationView,
    RegisterRequest,
    SessionView,
    SwitchOrganizationRequest,
    UserView,
)
from app.modules.auth.service import AuthContext, IssuedSession
from app.security.tokens import csrf_token_for

router = APIRouter(prefix="/auth", tags=["auth"])


async def build_session_view(db: AsyncSession, settings: Settings, ctx: AuthContext) -> SessionView:
    organizations = await service.list_user_organizations(db, ctx.user.id)
    return SessionView(
        user=UserView.model_validate(ctx.user),
        organization=OrganizationView.model_validate(ctx.organization),
        role=ctx.role,
        permissions=sorted(ctx.permissions),
        organizations=[
            OrganizationChoice(id=org.id, name=org.name, role=role) for org, role in organizations
        ],
        csrf_token=csrf_token_for(ctx.session.id, settings.secret_key.get_secret_value()),
    )


async def start_authenticated_response(
    db: AsyncSession, settings: Settings, response: Response, issued: IssuedSession
) -> SessionView:
    """Set the cookie for a freshly issued session and return the session payload."""
    ctx = await service.resolve_session(db, settings, issued.token)
    if ctx is None:  # pragma: no cover - the session was created in this transaction
        raise NotAuthenticated
    await bind_tenant(db, ctx.organization.id)
    set_session_cookie(response, settings, issued.token)
    return await build_session_view(db, settings, ctx)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    limiter: Limiter,
    client: Client,
) -> SessionView:
    """Create a company account with its first user as owner, and sign them in."""
    issued = await service.register(
        db,
        settings,
        limiter,
        organization_name=payload.organization_name,
        full_name=payload.full_name,
        email=payload.email,
        password=payload.password.get_secret_value(),
        client=client,
    )
    return await start_authenticated_response(db, settings, response, issued)


@router.post("/login")
async def login(
    payload: LoginRequest,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    limiter: Limiter,
    client: Client,
) -> SessionView:
    issued = await service.login(
        db,
        settings,
        limiter,
        email=payload.email,
        password=payload.password.get_secret_value(),
        client=client,
    )
    return await start_authenticated_response(db, settings, response, issued)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    auth: CurrentAuth, response: Response, db: DbSession, settings: AppSettings, client: Client
) -> None:
    await service.revoke(db, auth.session)
    record(
        db,
        AuditAction.LOGOUT,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        ip_address=client.ip,
    )
    clear_session_cookie(response, settings)


@router.get("/session")
async def current_session(auth: CurrentAuth, db: DbSession, settings: AppSettings) -> SessionView:
    return await build_session_view(db, settings, auth)


@router.post("/switch-organization")
async def switch_organization(
    payload: SwitchOrganizationRequest,
    auth: CurrentAuth,
    db: DbSession,
    settings: AppSettings,
    client: Client,
) -> SessionView:
    await service.switch_organization(db, auth, payload.organization_id, client)
    ctx = await service.reload_context(db, settings, auth.session.id)
    await bind_tenant(db, ctx.organization.id)
    return await build_session_view(db, settings, ctx)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    auth: CurrentAuth,
    db: DbSession,
    settings: AppSettings,
    limiter: Limiter,
    client: Client,
) -> None:
    """Change the password and sign out every other device."""
    await service.change_password(
        db,
        settings,
        limiter,
        auth,
        current_password=payload.current_password.get_secret_value(),
        new_password=payload.new_password.get_secret_value(),
        client=client,
    )


@router.get("/sessions")
async def list_sessions(
    auth: CurrentAuth, db: DbSession, settings: AppSettings
) -> list[ActiveSessionView]:
    sessions = await service.list_active_sessions(db, settings, auth.user.id)
    return [
        ActiveSessionView(
            id=session.id,
            created_at=session.created_at,
            last_seen_at=session.last_seen_at,
            ip_address=str(session.ip_address) if session.ip_address else None,
            user_agent=session.user_agent,
            current=session.id == auth.session.id,
        )
        for session in sessions
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    session_id: uuid.UUID,
    auth: CurrentAuth,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    client: Client,
) -> None:
    await service.revoke_own_session(db, auth, session_id, client)
    if session_id == auth.session.id:
        clear_session_cookie(response, settings)


@router.post("/sessions/revoke-others", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_other_sessions(auth: CurrentAuth, db: DbSession, client: Client) -> None:
    await service.revoke_user_sessions(db, auth.user.id, except_session_id=auth.session.id)
    record(
        db,
        AuditAction.SESSION_REVOKED,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        ip_address=client.ip,
        details={"scope": "other_sessions"},
    )
