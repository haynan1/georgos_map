import uuid
from datetime import datetime
from typing import Any

from app.core.schemas import (
    AnyPassword,
    Email,
    OpaqueToken,
    OrganizationName,
    PersonName,
    RequestModel,
    ResponseModel,
)
from app.security.permissions import Role


class UpdateOrganizationRequest(RequestModel):
    name: OrganizationName


class MemberView(ResponseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str
    role: Role
    joined_at: datetime
    is_you: bool


class UpdateMemberRequest(RequestModel):
    role: Role


class CreateInvitationRequest(RequestModel):
    email: Email
    role: Role


class InvitationView(ResponseModel):
    id: uuid.UUID
    email: str
    role: Role
    created_at: datetime
    expires_at: datetime


class CreatedInvitationView(InvitationView):
    # Returned exactly once. Only its hash is stored, so it cannot be shown again.
    token: str


class InvitationTokenRequest(RequestModel):
    token: OpaqueToken


class InvitationPreview(ResponseModel):
    organization_name: str
    email: str
    role: Role
    expires_at: datetime
    account_exists: bool


class AcceptInvitationRequest(RequestModel):
    token: OpaqueToken
    # Required only when the invited e-mail has no account yet.
    full_name: PersonName | None = None
    # For a new account this becomes their password (policy enforced in the service);
    # for an existing account it proves they own it.
    password: AnyPassword


class AuditEventView(ResponseModel):
    id: uuid.UUID
    action: str
    actor_user_id: uuid.UUID | None
    actor_name: str | None
    target_id: uuid.UUID | None
    ip_address: str | None
    details: dict[str, Any]
    created_at: datetime
