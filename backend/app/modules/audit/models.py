import uuid
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import Any

from sqlalchemy import ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKey


class AuditEvent(UUIDPrimaryKey, Base):
    """Append-only record of security-relevant actions.

    The application role is granted INSERT and SELECT only on this table (see the
    initial migration), so a compromised API cannot rewrite history.
    """

    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_organization_id_id", "organization_id", "id"),)

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE")
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[uuid.UUID | None]
    ip_address: Mapped[IPv4Address | IPv6Address | None] = mapped_column(INET)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
