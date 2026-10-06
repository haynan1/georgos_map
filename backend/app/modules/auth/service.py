"""Authentication and session lifecycle.

Functions here never touch HTTP: they take a database session plus plain values and
return domain objects, so they are reusable from routers, CLIs and tests alike.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import ColumnElement, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.client import ClientInfo
from app.core.config import Settings
from app.core.errors import (
    AppError,
    Conflict,
    IncorrectPassword,
    InvalidCredentials,
    NotAuthenticated,
    NotFound,
)
from app.modules.audit.service import AuditAction, record
from app.modules.auth.models import User, UserSession
from app.modules.organizations.models import Membership, Organization
from app.security import rate_limit
from app.security.passwords import hash_password, needs_rehash, verify_password
from app.security.permissions import Permission, Role, permissions_for
from app.security.rate_limit import RateLimiter
from app.security.tokens import digest_token, fingerprint, generate_token

# Writing last_seen_at on every request would turn every read into a write.
_LAST_SEEN_RESOLUTION = timedelta(minutes=1)
# Hard caps on list endpoints: nobody legitimately has more, and no query is unbounded.
MAX_LISTED_SESSIONS = 50
MAX_ORGANIZATIONS_PER_USER = 100


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class AuthContext:
    session: UserSession
    user: User
    organization: Organization
    membership: Membership

    @property
    def role(self) -> Role:
        return self.membership.role

    @property
    def permissions(self) -> frozenset[Permission]:
        return permissions_for(self.membership.role)


@dataclass(frozen=True, slots=True)
class IssuedSession:
    token: str
    session: UserSession


class NoOrganization(AppError):
    status_code = 403
    code = "no_organization"
    message = "Sua conta não está vinculada a nenhuma organização ativa."


async def issue_session(
    db: AsyncSession,
    settings: Settings,
    *,
    user: User,
    organization_id: uuid.UUID,
    client: ClientInfo,
) -> IssuedSession:
    """Always mints a fresh token, so a pre-authentication cookie can never be promoted
    to an authenticated one (session fixation)."""
    now = utcnow()
    token = generate_token()
    session = UserSession(
        token_hash=digest_token(token),
        user_id=user.id,
        organization_id=organization_id,
        created_at=now,
        last_seen_at=now,
        expires_at=now + settings.session_absolute_timeout,
        ip_address=client.ip,
        user_agent=client.user_agent,
    )
    db.add(session)
    user.last_login_at = now
    await db.flush()
    return IssuedSession(token=token, session=session)


async def register(
    db: AsyncSession,
    settings: Settings,
    limiter: RateLimiter,
    *,
    organization_name: str,
    full_name: str,
    email: str,
    password: str,
    client: ClientInfo,
) -> IssuedSession:
    secret = settings.secret_key.get_secret_value()
    await limiter.hit(rate_limit.REGISTER_PER_IP, fingerprint(client.ip_key, secret))

    duplicate = Conflict("Não foi possível concluir o cadastro com este e-mail.")
    if await db.scalar(select(User.id).where(User.email == email)) is not None:
        raise duplicate

    now = utcnow()
    user = User(
        email=email,
        full_name=full_name,
        password_hash=await hash_password(password),
        password_changed_at=now,
    )
    organization = Organization(name=organization_name)
    db.add_all([user, organization])
    try:
        await db.flush()
    except IntegrityError as exc:  # concurrent registration with the same e-mail
        raise duplicate from exc

    db.add(Membership(organization_id=organization.id, user_id=user.id, role=Role.OWNER))
    record(
        db,
        AuditAction.ORGANIZATION_CREATED,
        organization_id=organization.id,
        actor_user_id=user.id,
        ip_address=client.ip,
    )
    return await issue_session(
        db, settings, user=user, organization_id=organization.id, client=client
    )


async def login(
    db: AsyncSession,
    settings: Settings,
    limiter: RateLimiter,
    *,
    email: str,
    password: str,
    client: ClientInfo,
) -> IssuedSession:
    secret = settings.secret_key.get_secret_value()
    account_key = fingerprint(email, secret)
    await limiter.hit(rate_limit.LOGIN_PER_IP, fingerprint(client.ip_key, secret))
    # Count the attempt as a failure *before* checking the password. The counter is an
    # atomic upsert, so parallel guesses cannot slip past the budget; success clears it.
    await limiter.hit(rate_limit.LOGIN_FAILURES_PER_ACCOUNT, account_key)

    user = await db.scalar(select(User).where(User.email == email))
    password_ok = await verify_password(user.password_hash if user else None, password)

    if user is None or not password_ok or not user.is_active:
        record(
            db,
            AuditAction.LOGIN_FAILED,
            organization_id=None,
            actor_user_id=user.id if user else None,
            ip_address=client.ip,
        )
        # Persist the audit trail even though the request ends in an error.
        await db.commit()
        raise InvalidCredentials

    await limiter.clear(rate_limit.LOGIN_FAILURES_PER_ACCOUNT, account_key)
    if needs_rehash(user.password_hash):
        user.password_hash = await hash_password(password)

    organization_id = await _preferred_organization(db, user.id)
    if organization_id is None:
        raise NoOrganization

    issued = await issue_session(
        db, settings, user=user, organization_id=organization_id, client=client
    )
    record(
        db,
        AuditAction.LOGIN_SUCCEEDED,
        organization_id=organization_id,
        actor_user_id=user.id,
        ip_address=client.ip,
    )
    return issued


async def _preferred_organization(db: AsyncSession, user_id: uuid.UUID) -> uuid.UUID | None:
    """The organization of the user's most recent session, else their oldest membership."""
    member_of = select(Membership.organization_id).where(Membership.user_id == user_id)
    recent = await db.scalar(
        select(UserSession.organization_id)
        .where(
            UserSession.user_id == user_id,
            UserSession.organization_id.in_(member_of),
        )
        .order_by(UserSession.created_at.desc())
        .limit(1)
    )
    if recent is not None:
        return recent
    return await db.scalar(member_of.order_by(Membership.created_at).limit(1))


async def resolve_session(db: AsyncSession, settings: Settings, token: str) -> AuthContext | None:
    """Validate a session token and load the full auth context in one round trip."""
    return await _load_context(db, settings, UserSession.token_hash == digest_token(token))


async def reload_context(
    db: AsyncSession, settings: Settings, session_id: uuid.UUID
) -> AuthContext:
    ctx = await _load_context(db, settings, UserSession.id == session_id)
    if ctx is None:
        raise NotAuthenticated
    return ctx


async def _load_context(
    db: AsyncSession, settings: Settings, criterion: ColumnElement[bool]
) -> AuthContext | None:
    """A session is valid only while: not revoked, inside both the idle and the absolute
    timeout, the user is active, and the user still belongs to the session's organization.
    """
    now = utcnow()
    row = (
        await db.execute(
            select(UserSession, User, Organization, Membership)
            .join(User, User.id == UserSession.user_id)
            .join(Organization, Organization.id == UserSession.organization_id)
            .join(
                Membership,
                (Membership.user_id == UserSession.user_id)
                & (Membership.organization_id == UserSession.organization_id),
            )
            .where(
                criterion,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
                UserSession.last_seen_at > now - settings.session_idle_timeout,
                User.is_active.is_(True),
            )
        )
    ).one_or_none()
    if row is None:
        return None

    session, user, organization, membership = row
    if now - session.last_seen_at >= _LAST_SEEN_RESOLUTION:
        session.last_seen_at = now
    return AuthContext(session=session, user=user, organization=organization, membership=membership)


async def revoke(db: AsyncSession, session: UserSession) -> None:
    session.revoked_at = utcnow()
    await db.flush()


async def revoke_user_sessions(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    organization_id: uuid.UUID | None = None,
    except_session_id: uuid.UUID | None = None,
) -> int:
    query = update(UserSession).where(
        UserSession.user_id == user_id, UserSession.revoked_at.is_(None)
    )
    if organization_id is not None:
        query = query.where(UserSession.organization_id == organization_id)
    if except_session_id is not None:
        query = query.where(UserSession.id != except_session_id)
    result = await db.execute(query.values(revoked_at=utcnow()))
    return int(result.rowcount)  # type: ignore[attr-defined]


async def list_active_sessions(
    db: AsyncSession, settings: Settings, user_id: uuid.UUID
) -> list[UserSession]:
    now = utcnow()
    return list(
        (
            await db.scalars(
                select(UserSession)
                .where(
                    UserSession.user_id == user_id,
                    UserSession.revoked_at.is_(None),
                    UserSession.expires_at > now,
                    UserSession.last_seen_at > now - settings.session_idle_timeout,
                )
                .order_by(UserSession.last_seen_at.desc())
                .limit(MAX_LISTED_SESSIONS)
            )
        ).all()
    )


async def revoke_own_session(
    db: AsyncSession, ctx: AuthContext, session_id: uuid.UUID, client: ClientInfo
) -> UserSession:
    target = await db.scalar(
        select(UserSession).where(
            UserSession.id == session_id,
            UserSession.user_id == ctx.user.id,
            UserSession.revoked_at.is_(None),
        )
    )
    if target is None:
        raise NotFound("Sessão não encontrada.")
    await revoke(db, target)
    record(
        db,
        AuditAction.SESSION_REVOKED,
        organization_id=ctx.organization.id,
        actor_user_id=ctx.user.id,
        target_id=target.id,
        ip_address=client.ip,
    )
    return target


async def change_password(
    db: AsyncSession,
    settings: Settings,
    limiter: RateLimiter,
    ctx: AuthContext,
    *,
    current_password: str,
    new_password: str,
    client: ClientInfo,
) -> None:
    await limiter.hit(rate_limit.PASSWORD_CHANGE_PER_USER, str(ctx.user.id))
    if not await verify_password(ctx.user.password_hash, current_password):
        raise IncorrectPassword("Senha atual incorreta.")
    if current_password == new_password:
        raise AppError("A nova senha precisa ser diferente da atual.")

    ctx.user.password_hash = await hash_password(new_password)
    ctx.user.password_changed_at = utcnow()
    # A password change is the standard response to a suspected compromise: every other
    # device is signed out immediately.
    await revoke_user_sessions(db, ctx.user.id, except_session_id=ctx.session.id)
    record(
        db,
        AuditAction.PASSWORD_CHANGED,
        organization_id=ctx.organization.id,
        actor_user_id=ctx.user.id,
        ip_address=client.ip,
    )


async def switch_organization(
    db: AsyncSession, ctx: AuthContext, organization_id: uuid.UUID, client: ClientInfo
) -> None:
    is_member = await db.scalar(
        select(Membership.id).where(
            Membership.user_id == ctx.user.id, Membership.organization_id == organization_id
        )
    )
    if is_member is None:
        raise NotFound("Organização não encontrada.")
    ctx.session.organization_id = organization_id
    record(
        db,
        AuditAction.ORGANIZATION_SWITCHED,
        organization_id=organization_id,
        actor_user_id=ctx.user.id,
        ip_address=client.ip,
    )
    await db.flush()


async def list_user_organizations(
    db: AsyncSession, user_id: uuid.UUID
) -> list[tuple[Organization, Role]]:
    rows = await db.execute(
        select(Organization, Membership.role)
        .join(Membership, Membership.organization_id == Organization.id)
        .where(Membership.user_id == user_id)
        .order_by(Organization.name)
        .limit(MAX_ORGANIZATIONS_PER_USER)
    )
    return [(organization, role) for organization, role in rows]
