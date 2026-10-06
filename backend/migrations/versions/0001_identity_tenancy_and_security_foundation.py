"""Identity, tenancy and security foundation.

Creates users, organizations, memberships, invitations, sessions, the audit trail and
rate-limit buckets, and grants the runtime role (APP_DB_USER) exactly what the API needs:

- DML on every table created by the owner from now on (default privileges), so tables
  added by later migrations are usable without extra grants;
- INSERT/SELECT only on ``audit_events``: the trail is append-only for the API.

Revision ID: 0001
Revises:
Create Date: 2026-10-06
"""

import os
import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLES = ("owner", "admin", "manager", "operator", "viewer")


def _app_role() -> str:
    role = os.environ.get("APP_DB_USER", "")
    # DDL cannot take bind parameters, so the identifier is validated before interpolation.
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", role):
        raise RuntimeError("APP_DB_USER must be a lowercase PostgreSQL identifier")
    return role


def _id() -> sa.Column[sa.Uuid]:
    return sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), primary_key=True)


def _timestamp(
    name: str, *, nullable: bool = False, default: bool = True
) -> sa.Column[sa.DateTime]:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.text("now()") if default else None,
        nullable=nullable,
    )


def _role(table: str) -> tuple[sa.Column[str], sa.CheckConstraint]:
    allowed = ", ".join(f"'{role}'" for role in ROLES)
    return (
        sa.Column("role", sa.String(16), nullable=False),
        sa.CheckConstraint(f"role IN ({allowed})", name=op.f(f"ck_{table}_role")),
    )


def upgrade() -> None:
    app_role = _app_role()

    op.execute(f'GRANT USAGE ON SCHEMA public TO "{app_role}"')
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "{app_role}"'
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f'GRANT USAGE, SELECT ON SEQUENCES TO "{app_role}"'
    )
    # Readiness checks confirm migrations ran by reading the version table.
    op.execute(f'GRANT SELECT ON alembic_version TO "{app_role}"')

    op.create_table(
        "organizations",
        _id(),
        sa.Column("name", sa.String(120), nullable=False),
        _timestamp("created_at"),
        _timestamp("updated_at"),
    )

    op.create_table(
        "users",
        _id(),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        _timestamp("password_changed_at", nullable=True, default=False),
        _timestamp("last_login_at", nullable=True, default=False),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.CheckConstraint("email = lower(email)", name=op.f("ck_users_email_lowercase")),
    )

    role_column, role_check = _role("memberships")
    op.create_table(
        "memberships",
        _id(),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey(
                "organizations.id",
                ondelete="CASCADE",
                name=op.f("fk_memberships_organization_id_organizations"),
            ),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey(
                "users.id", ondelete="CASCADE", name=op.f("fk_memberships_user_id_users")
            ),
            nullable=False,
        ),
        role_column,
        _timestamp("created_at"),
        _timestamp("updated_at"),
        role_check,
        sa.UniqueConstraint(
            "organization_id", "user_id", name=op.f("uq_memberships_organization_id_user_id")
        ),
    )
    op.create_index(op.f("ix_memberships_user_id"), "memberships", ["user_id"])

    role_column, role_check = _role("invitations")
    op.create_table(
        "invitations",
        _id(),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey(
                "organizations.id",
                ondelete="CASCADE",
                name=op.f("fk_invitations_organization_id_organizations"),
            ),
            nullable=False,
        ),
        sa.Column("email", sa.String(320), nullable=False),
        role_column,
        sa.Column("token_hash", sa.LargeBinary(32), nullable=False),
        sa.Column(
            "invited_by_user_id",
            sa.Uuid(),
            sa.ForeignKey(
                "users.id",
                ondelete="SET NULL",
                name=op.f("fk_invitations_invited_by_user_id_users"),
            ),
            nullable=True,
        ),
        _timestamp("created_at"),
        _timestamp("expires_at", default=False),
        _timestamp("accepted_at", nullable=True, default=False),
        _timestamp("revoked_at", nullable=True, default=False),
        role_check,
        sa.UniqueConstraint("token_hash", name=op.f("uq_invitations_token_hash")),
    )
    op.create_index(
        "ix_invitations_organization_id_pending",
        "invitations",
        ["organization_id"],
        postgresql_where=sa.text("accepted_at IS NULL AND revoked_at IS NULL"),
    )

    op.create_table(
        "user_sessions",
        _id(),
        sa.Column("token_hash", sa.LargeBinary(32), nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey(
                "users.id", ondelete="CASCADE", name=op.f("fk_user_sessions_user_id_users")
            ),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey(
                "organizations.id",
                ondelete="CASCADE",
                name=op.f("fk_user_sessions_organization_id_organizations"),
            ),
            nullable=False,
        ),
        _timestamp("created_at"),
        _timestamp("last_seen_at"),
        _timestamp("expires_at", default=False),
        _timestamp("revoked_at", nullable=True, default=False),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.UniqueConstraint("token_hash", name=op.f("uq_user_sessions_token_hash")),
    )
    op.create_index(op.f("ix_user_sessions_organization_id"), "user_sessions", ["organization_id"])
    op.create_index(
        "ix_user_sessions_user_id_created_at", "user_sessions", ["user_id", "created_at"]
    )

    op.create_table(
        "audit_events",
        _id(),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey(
                "organizations.id",
                ondelete="CASCADE",
                name=op.f("fk_audit_events_organization_id_organizations"),
            ),
            nullable=True,
        ),
        sa.Column(
            "actor_user_id",
            sa.Uuid(),
            sa.ForeignKey(
                "users.id", ondelete="SET NULL", name=op.f("fk_audit_events_actor_user_id_users")
            ),
            nullable=True,
        ),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        _timestamp("created_at"),
    )
    op.create_index("ix_audit_events_organization_id_id", "audit_events", ["organization_id", "id"])
    op.execute(f'REVOKE UPDATE, DELETE ON audit_events FROM "{app_role}"')

    op.create_table(
        "rate_limit_buckets",
        sa.Column("key", sa.String(96), primary_key=True),
        _timestamp("window_started_at", default=False),
        sa.Column("hits", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    app_role = _app_role()
    op.drop_table("rate_limit_buckets")
    op.drop_table("audit_events")
    op.drop_table("user_sessions")
    op.drop_table("invitations")
    op.drop_table("memberships")
    op.drop_table("users")
    op.drop_table("organizations")
    op.execute(f'REVOKE SELECT ON alembic_version FROM "{app_role}"')
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f'REVOKE USAGE, SELECT ON SEQUENCES FROM "{app_role}"'
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f'REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM "{app_role}"'
    )
    op.execute(f'REVOKE USAGE ON SCHEMA public FROM "{app_role}"')
