import uuid
from datetime import datetime

from app.core.schemas import (
    AnyPassword,
    Email,
    NewPassword,
    OrganizationName,
    PersonName,
    RequestModel,
    ResponseModel,
)
from app.security.permissions import Permission, Role


class RegisterRequest(RequestModel):
    organization_name: OrganizationName
    full_name: PersonName
    email: Email
    password: NewPassword


class LoginRequest(RequestModel):
    email: Email
    password: AnyPassword


class ChangePasswordRequest(RequestModel):
    current_password: AnyPassword
    new_password: NewPassword


class SwitchOrganizationRequest(RequestModel):
    organization_id: uuid.UUID


class UserView(ResponseModel):
    id: uuid.UUID
    email: str
    full_name: str


class OrganizationView(ResponseModel):
    id: uuid.UUID
    name: str


class OrganizationChoice(ResponseModel):
    id: uuid.UUID
    name: str
    role: Role


class SessionView(ResponseModel):
    """Everything the frontend needs to render an authenticated shell."""

    user: UserView
    organization: OrganizationView
    role: Role
    permissions: list[Permission]
    organizations: list[OrganizationChoice]
    csrf_token: str


class ActiveSessionView(ResponseModel):
    id: uuid.UUID
    created_at: datetime
    last_seen_at: datetime
    ip_address: str | None
    user_agent: str | None
    current: bool
