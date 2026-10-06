import uuid
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address

from sqlalchemy import CheckConstraint, ForeignKey, Index, LargeBinary, String, text
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPrimaryKey


class User(UUIDPrimaryKey, Timestamps, Base):
    """A person. Identity is global; access to company data comes from memberships."""

    __tablename__ = "users"
    __table_args__ = (CheckConstraint("email = lower(email)", name="email_lowercase"),)

    email: Mapped[str] = mapped_column(String(320), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    password_changed_at: Mapped[datetime | None]
    last_login_at: Mapped[datetime | None]


class UserSession(UUIDPrimaryKey, Base):
    """Server-side session. The browser only holds an opaque token whose SHA-256 is here,
    so sessions can be listed and revoked individually, unlike stateless JWTs."""

    __tablename__ = "user_sessions"
    # Serves every per-user lookup: active-session lists, bulk revocation and "which
    # organization did this user use last" at login.
    __table_args__ = (Index("ix_user_sessions_user_id_created_at", "user_id", "created_at"),)

    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    last_seen_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    ip_address: Mapped[IPv4Address | IPv6Address | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(String(512))
