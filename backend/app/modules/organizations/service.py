"""Organization administration: profile, members, invitations."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from fastapi import status
from sqlalchemy import ColumnElement, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.client import ClientInfo
from app.core.config import Settings
from app.core.errors import AppError, Conflict, InvalidCredentials, NotFound, PermissionDenied
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import AuditAction, record
from app.modules.auth.models import User
from app.modules.auth.service import (
    AuthContext,
    IssuedSession,
    issue_session,
    revoke_user_sessions,
    utcnow,
)
from app.modules.organizations.models import Invitation, Membership, Organization
from app.security import rate_limit
from app.security.passwords import PASSWORD_MIN_LENGTH, hash_password, verify_password
from app.security.permissions import Role, can_assign, can_manage
from app.security.rate_limit import RateLimiter
from app.security.tokens import digest_token, fingerprint, generate_token


class InvitationUnavailable(AppError):
    status_code = status.HTTP_410_GONE
    code = "invitation_unavailable"
    message = "Este convite expirou, foi cancelado ou já foi utilizado."


class WeakPassword(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "weak_password"
    message = f"A senha precisa ter pelo menos {PASSWORD_MIN_LENGTH} caracteres."


# Hard caps: list endpoints are never unbounded. Paginate before an organization nears these.
MAX_LISTED_MEMBERS = 500
MAX_LISTED_INVITATIONS = 200


@dataclass(frozen=True, slots=True)
class MemberRow:
    membership: Membership
    user: User


async def update_organization(
    db: AsyncSession, auth: AuthContext, *, name: str, client: ClientInfo
) -> Organization:
    previous = auth.organization.name
    auth.organization.name = name
    record(
        db,
        AuditAction.ORGANIZATION_UPDATED,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        ip_address=client.ip,
        details={"name": {"from": previous, "to": name}},
    )
    await db.flush()
    return auth.organization


async def list_members(db: AsyncSession, organization_id: uuid.UUID) -> list[MemberRow]:
    rows = await db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.organization_id == organization_id)
        .order_by(User.full_name)
        .limit(MAX_LISTED_MEMBERS)
    )
    return [MemberRow(membership=m, user=u) for m, u in rows]


async def _lock_for_management(
    db: AsyncSession, auth: AuthContext, membership_id: uuid.UUID
) -> tuple[Membership, Membership]:
    """Lock the actor's and the target's memberships, then re-check authority.

    Rows are locked in id order (no deadlocks) and re-read from the database, so two owners
    removing or demoting each other at the same instant cannot leave the company without
    an owner: the second transaction sees the first one's outcome.
    """
    if membership_id == auth.membership.id:
        raise Conflict("Você não pode alterar o próprio acesso.")
    rows = await db.scalars(
        select(Membership)
        .where(
            Membership.organization_id == auth.organization.id,
            Membership.id.in_([auth.membership.id, membership_id]),
        )
        .order_by(Membership.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    by_id = {membership.id: membership for membership in rows}
    target = by_id.get(membership_id)
    actor = by_id.get(auth.membership.id)
    if target is None:
        raise NotFound("Membro não encontrado.")
    if actor is None:
        raise PermissionDenied
    if not can_manage(actor.role, target.role):
        raise PermissionDenied("Você não pode gerenciar um membro com papel igual ou superior.")
    return actor, target


async def change_member_role(
    db: AsyncSession,
    auth: AuthContext,
    membership_id: uuid.UUID,
    *,
    role: Role,
    client: ClientInfo,
) -> Membership:
    actor, target = await _lock_for_management(db, auth, membership_id)
    if not can_assign(actor.role, role):
        raise PermissionDenied("Você não pode conceder um papel superior ao seu.")

    previous = target.role
    target.role = role
    record(
        db,
        AuditAction.MEMBER_ROLE_CHANGED,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        target_id=target.user_id,
        ip_address=client.ip,
        details={"role": {"from": previous.value, "to": role.value}},
    )
    await db.flush()
    return target


async def remove_member(
    db: AsyncSession, auth: AuthContext, membership_id: uuid.UUID, *, client: ClientInfo
) -> None:
    _, target = await _lock_for_management(db, auth, membership_id)
    await db.delete(target)
    # Access ends now, not when their session would have expired.
    await revoke_user_sessions(db, target.user_id, organization_id=auth.organization.id)
    record(
        db,
        AuditAction.MEMBER_REMOVED,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        target_id=target.user_id,
        ip_address=client.ip,
        details={"role": target.role.value},
    )
    await db.flush()


def _pending(now: datetime) -> list[ColumnElement[bool]]:
    return [
        Invitation.accepted_at.is_(None),
        Invitation.revoked_at.is_(None),
        Invitation.expires_at > now,
    ]


async def list_invitations(db: AsyncSession, organization_id: uuid.UUID) -> list[Invitation]:
    return list(
        (
            await db.scalars(
                select(Invitation)
                .where(Invitation.organization_id == organization_id, *_pending(utcnow()))
                .order_by(Invitation.created_at.desc())
                .limit(MAX_LISTED_INVITATIONS)
            )
        ).all()
    )


async def create_invitation(
    db: AsyncSession,
    settings: Settings,
    auth: AuthContext,
    *,
    email: str,
    role: Role,
    client: ClientInfo,
) -> tuple[Invitation, str]:
    if not can_assign(auth.role, role):
        raise PermissionDenied("Você não pode convidar alguém com papel superior ao seu.")

    already_member = await db.scalar(
        select(Membership.id)
        .join(User, User.id == Membership.user_id)
        .where(Membership.organization_id == auth.organization.id, User.email == email)
    )
    if already_member is not None:
        raise Conflict("Esta pessoa já faz parte da organização.")

    now = utcnow()
    # Re-inviting supersedes any pending link for the same address.
    await db.execute(
        update(Invitation)
        .where(
            Invitation.organization_id == auth.organization.id,
            Invitation.email == email,
            Invitation.accepted_at.is_(None),
            Invitation.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )

    token = generate_token()
    invitation = Invitation(
        organization_id=auth.organization.id,
        email=email,
        role=role,
        token_hash=digest_token(token),
        invited_by_user_id=auth.user.id,
        created_at=now,
        expires_at=now + settings.invitation_ttl,
    )
    db.add(invitation)
    await db.flush()
    record(
        db,
        AuditAction.INVITATION_CREATED,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        target_id=invitation.id,
        ip_address=client.ip,
        details={"role": role.value},
    )
    return invitation, token


async def revoke_invitation(
    db: AsyncSession, auth: AuthContext, invitation_id: uuid.UUID, *, client: ClientInfo
) -> None:
    invitation = await db.scalar(
        select(Invitation).where(
            Invitation.id == invitation_id,
            Invitation.organization_id == auth.organization.id,
            *_pending(utcnow()),
        )
    )
    if invitation is None:
        raise NotFound("Convite não encontrado.")
    if not can_assign(auth.role, invitation.role):
        raise PermissionDenied
    invitation.revoked_at = utcnow()
    record(
        db,
        AuditAction.INVITATION_REVOKED,
        organization_id=auth.organization.id,
        actor_user_id=auth.user.id,
        target_id=invitation.id,
        ip_address=client.ip,
    )
    await db.flush()


async def _pending_invitation(
    db: AsyncSession, token: str, *, for_update: bool = False
) -> tuple[Invitation, Organization]:
    query = (
        select(Invitation, Organization)
        .join(Organization, Organization.id == Invitation.organization_id)
        .where(Invitation.token_hash == digest_token(token), *_pending(utcnow()))
    )
    if for_update:
        # Serializes concurrent accepts of the same link: the invitation is single-use.
        query = query.with_for_update(of=Invitation)
    row = (await db.execute(query)).one_or_none()
    if row is None:
        raise InvitationUnavailable
    invitation, organization = row
    return invitation, organization


async def preview_invitation(
    db: AsyncSession, settings: Settings, limiter: RateLimiter, *, token: str, client: ClientInfo
) -> tuple[Invitation, Organization, bool]:
    secret = settings.secret_key.get_secret_value()
    await limiter.hit(rate_limit.INVITATION_PER_IP, fingerprint(client.ip_key, secret))
    invitation, organization = await _pending_invitation(db, token)
    account_exists = (
        await db.scalar(select(User.id).where(User.email == invitation.email))
    ) is not None
    return invitation, organization, account_exists


async def accept_invitation(
    db: AsyncSession,
    settings: Settings,
    limiter: RateLimiter,
    *,
    token: str,
    full_name: str | None,
    password: str,
    client: ClientInfo,
) -> IssuedSession:
    secret = settings.secret_key.get_secret_value()
    await limiter.hit(rate_limit.INVITATION_PER_IP, fingerprint(client.ip_key, secret))
    invitation, organization = await _pending_invitation(db, token, for_update=True)

    user = await db.scalar(select(User).where(User.email == invitation.email))
    if user is None:
        user = await _create_invited_user(db, invitation.email, full_name, password)
    else:
        # The link alone is not proof of owning an existing account. Same atomic
        # failure budget as the login endpoint, so this is not a side door for guessing.
        account_key = fingerprint(invitation.email, secret)
        await limiter.hit(rate_limit.LOGIN_FAILURES_PER_ACCOUNT, account_key)
        if not user.is_active or not await verify_password(user.password_hash, password):
            raise InvalidCredentials("Senha incorreta para a conta existente.")
        await limiter.clear(rate_limit.LOGIN_FAILURES_PER_ACCOUNT, account_key)

    db.add(Membership(organization_id=organization.id, user_id=user.id, role=invitation.role))
    invitation.accepted_at = utcnow()
    try:
        await db.flush()
    except IntegrityError as exc:
        raise Conflict("Você já faz parte desta organização.") from exc

    record(
        db,
        AuditAction.MEMBER_JOINED,
        organization_id=organization.id,
        actor_user_id=user.id,
        target_id=invitation.id,
        ip_address=client.ip,
        details={"role": invitation.role.value},
    )
    return await issue_session(
        db, settings, user=user, organization_id=organization.id, client=client
    )


async def _create_invited_user(
    db: AsyncSession, email: str, full_name: str | None, password: str
) -> User:
    if full_name is None:
        raise AppError("Informe seu nome para criar a conta.")
    if len(password) < PASSWORD_MIN_LENGTH or not password.strip():
        raise WeakPassword
    user = User(
        email=email,
        full_name=full_name,
        password_hash=await hash_password(password),
        password_changed_at=utcnow(),
    )
    db.add(user)
    await db.flush()
    return user


async def list_audit_events(
    db: AsyncSession, organization_id: uuid.UUID, *, before: uuid.UUID | None, limit: int
) -> list[tuple[AuditEvent, str | None]]:
    # UUIDv7 ids are time-ordered, so the id alone is a stable keyset cursor.
    query = (
        select(AuditEvent, User.full_name)
        .outerjoin(User, User.id == AuditEvent.actor_user_id)
        .where(AuditEvent.organization_id == organization_id)
        .order_by(AuditEvent.id.desc())
        .limit(limit)
    )
    if before is not None:
        query = query.where(AuditEvent.id < before)
    return [(event, name) for event, name in await db.execute(query)]
