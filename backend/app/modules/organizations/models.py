import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPrimaryKey
from app.security.permissions import Role

# Stored as constrained VARCHAR rather than a native PG enum: adding a role later is a
# plain CHECK change instead of an ALTER TYPE that cannot run inside a transaction.
RoleColumn = Enum(
    Role,
    name="role",
    native_enum=False,
    create_constraint=False,
    length=16,
    values_callable=lambda roles: [role.value for role in roles],
)


def _role_check() -> CheckConstraint:
    allowed = ", ".join(f"'{role.value}'" for role in Role)
    return CheckConstraint(f"role IN ({allowed})", name="role")


class Organization(UUIDPrimaryKey, Timestamps, Base):
    """A customer company (tenant). Every business record belongs to exactly one."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(120))


class Membership(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("organization_id", "user_id"), _role_check())

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[Role] = mapped_column(RoleColumn)


class Invitation(UUIDPrimaryKey, Base):
    """Single-use link that lets someone join an organization with a preset role.

    Links are shared by the admin through any channel (e-mail, WhatsApp), so no outbound
    e-mail infrastructure is required to onboard a team.
    """

    __tablename__ = "invitations"
    __table_args__ = (
        _role_check(),
        Index(
            "ix_invitations_organization_id_pending",
            "organization_id",
            postgresql_where=text("accepted_at IS NULL AND revoked_at IS NULL"),
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE")
    )
    email: Mapped[str] = mapped_column(String(320))
    role: Mapped[Role] = mapped_column(RoleColumn)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    expires_at: Mapped[datetime]
    accepted_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]
