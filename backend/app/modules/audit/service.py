import uuid
from enum import StrEnum
from ipaddress import IPv4Address, IPv6Address
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditEvent


class AuditAction(StrEnum):
    LOGIN_SUCCEEDED = "auth.login_succeeded"
    LOGIN_FAILED = "auth.login_failed"
    LOGOUT = "auth.logout"
    PASSWORD_CHANGED = "auth.password_changed"  # noqa: S105 - an event name, not a secret
    SESSION_REVOKED = "auth.session_revoked"
    ORGANIZATION_SWITCHED = "auth.organization_switched"
    ORGANIZATION_CREATED = "organization.created"
    ORGANIZATION_UPDATED = "organization.updated"
    MEMBER_JOINED = "member.joined"
    MEMBER_ROLE_CHANGED = "member.role_changed"
    MEMBER_REMOVED = "member.removed"
    INVITATION_CREATED = "invitation.created"
    INVITATION_REVOKED = "invitation.revoked"


def record(
    db: AsyncSession,
    action: AuditAction,
    *,
    organization_id: uuid.UUID | None,
    actor_user_id: uuid.UUID | None,
    ip_address: IPv4Address | IPv6Address | None,
    target_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Stage an audit event in the caller's unit of work, so it commits atomically with
    the change it describes."""
    db.add(
        AuditEvent(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action=action.value,
            target_id=target_id,
            ip_address=ip_address,
            details=details or {},
        )
    )
