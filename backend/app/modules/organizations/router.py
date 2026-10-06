import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.modules.auth.dependencies import (
    AppSettings,
    Client,
    CurrentAuth,
    DbSession,
    Limiter,
    require,
)
from app.modules.auth.router import start_authenticated_response
from app.modules.auth.schemas import OrganizationView, SessionView
from app.modules.auth.service import AuthContext
from app.modules.organizations import service
from app.modules.organizations.schemas import (
    AcceptInvitationRequest,
    AuditEventView,
    CreatedInvitationView,
    CreateInvitationRequest,
    InvitationPreview,
    InvitationTokenRequest,
    InvitationView,
    MemberView,
    UpdateMemberRequest,
    UpdateOrganizationRequest,
)
from app.security.permissions import Permission

router = APIRouter(prefix="/organization", tags=["organization"])
invitations_router = APIRouter(prefix="/invitations", tags=["invitations"])

CanReadMembers = Annotated[AuthContext, require(Permission.MEMBERS_READ)]
CanManageMembers = Annotated[AuthContext, require(Permission.MEMBERS_MANAGE)]
CanUpdateOrganization = Annotated[AuthContext, require(Permission.ORGANIZATION_UPDATE)]
CanReadAudit = Annotated[AuthContext, require(Permission.AUDIT_READ)]


def _member_view(row: service.MemberRow, auth: AuthContext) -> MemberView:
    return MemberView(
        id=row.membership.id,
        user_id=row.user.id,
        full_name=row.user.full_name,
        email=row.user.email,
        role=row.membership.role,
        joined_at=row.membership.created_at,
        is_you=row.user.id == auth.user.id,
    )


@router.get("")
async def get_organization(auth: CurrentAuth) -> OrganizationView:
    return OrganizationView.model_validate(auth.organization)


@router.patch("")
async def update_organization(
    payload: UpdateOrganizationRequest, auth: CanUpdateOrganization, db: DbSession, client: Client
) -> OrganizationView:
    organization = await service.update_organization(db, auth, name=payload.name, client=client)
    return OrganizationView.model_validate(organization)


@router.get("/members")
async def list_members(auth: CanReadMembers, db: DbSession) -> list[MemberView]:
    rows = await service.list_members(db, auth.organization.id)
    return [_member_view(row, auth) for row in rows]


@router.patch("/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_member(
    membership_id: uuid.UUID,
    payload: UpdateMemberRequest,
    auth: CanManageMembers,
    db: DbSession,
    client: Client,
) -> None:
    await service.change_member_role(db, auth, membership_id, role=payload.role, client=client)


@router.delete("/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    membership_id: uuid.UUID, auth: CanManageMembers, db: DbSession, client: Client
) -> None:
    await service.remove_member(db, auth, membership_id, client=client)


@router.get("/invitations")
async def list_invitations(auth: CanManageMembers, db: DbSession) -> list[InvitationView]:
    invitations = await service.list_invitations(db, auth.organization.id)
    return [InvitationView.model_validate(invitation) for invitation in invitations]


@router.post("/invitations", status_code=status.HTTP_201_CREATED)
async def create_invitation(
    payload: CreateInvitationRequest,
    auth: CanManageMembers,
    db: DbSession,
    settings: AppSettings,
    client: Client,
) -> CreatedInvitationView:
    invitation, token = await service.create_invitation(
        db, settings, auth, email=payload.email, role=payload.role, client=client
    )
    return CreatedInvitationView(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        created_at=invitation.created_at,
        expires_at=invitation.expires_at,
        token=token,
    )


@router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invitation(
    invitation_id: uuid.UUID, auth: CanManageMembers, db: DbSession, client: Client
) -> None:
    await service.revoke_invitation(db, auth, invitation_id, client=client)


@router.get("/audit-events")
async def list_audit_events(
    auth: CanReadAudit,
    db: DbSession,
    before: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[AuditEventView]:
    rows = await service.list_audit_events(db, auth.organization.id, before=before, limit=limit)
    return [
        AuditEventView(
            id=event.id,
            action=event.action,
            actor_user_id=event.actor_user_id,
            actor_name=actor_name,
            target_id=event.target_id,
            ip_address=str(event.ip_address) if event.ip_address else None,
            details=event.details,
            created_at=event.created_at,
        )
        for event, actor_name in rows
    ]


# Invitation tokens travel in request bodies, never in URLs, so they cannot leak through
# access logs, browser history or Referer headers.


@invitations_router.post("/preview")
async def preview_invitation(
    payload: InvitationTokenRequest,
    db: DbSession,
    settings: AppSettings,
    limiter: Limiter,
    client: Client,
) -> InvitationPreview:
    invitation, organization, account_exists = await service.preview_invitation(
        db, settings, limiter, token=payload.token, client=client
    )
    return InvitationPreview(
        organization_name=organization.name,
        email=invitation.email,
        role=invitation.role,
        expires_at=invitation.expires_at,
        account_exists=account_exists,
    )


@invitations_router.post("/accept")
async def accept_invitation(
    payload: AcceptInvitationRequest,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    limiter: Limiter,
    client: Client,
) -> SessionView:
    issued = await service.accept_invitation(
        db,
        settings,
        limiter,
        token=payload.token,
        full_name=payload.full_name,
        password=payload.password.get_secret_value(),
        client=client,
    )
    return await start_authenticated_response(db, settings, response, issued)
