"""Engine, session factory and the tenant context that powers row-level security.

Tenant isolation has two layers:

1. Application layer: every tenant-scoped query filters by the authenticated
   organization (enforced in services).
2. Database layer: tenant tables carry a PostgreSQL row-level-security policy that reads
   ``app.organization_id``. The API connects with a non-owner role, so a missing filter
   returns zero rows instead of another company's data.

The organization id is applied with ``set_config(..., is_local => true)`` at the start of
*every* transaction the session opens, so it can never leak to another request through
the connection pool, and a session without a tenant sees no tenant rows at all.
"""

import uuid
from collections.abc import AsyncIterator

from sqlalchemy import Connection, event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, SessionTransaction
from starlette.requests import Request

from app.core.config import Settings

TENANT_SETTING = "app.organization_id"
_TENANT_INFO_KEY = "organization_id"
_SET_TENANT = text("SELECT set_config(:name, :value, true)")


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.database_url.get_secret_value(),
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,
        connect_args={"server_settings": {"application_name": "georgos-api"}},
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@event.listens_for(Session, "after_begin")
def _apply_tenant_on_begin(
    session: Session, _transaction: SessionTransaction, connection: Connection
) -> None:
    organization_id = session.info.get(_TENANT_INFO_KEY)
    if organization_id is not None:
        connection.execute(_SET_TENANT, {"name": TENANT_SETTING, "value": str(organization_id)})


async def bind_tenant(session: AsyncSession, organization_id: uuid.UUID) -> None:
    """Scope ``session`` to one organization for the rest of its lifetime."""
    session.info[_TENANT_INFO_KEY] = organization_id
    if session.in_transaction():
        await session.execute(_SET_TENANT, {"name": TENANT_SETTING, "value": str(organization_id)})


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """Request-scoped unit of work: commits when the endpoint succeeds, rolls back on error."""
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        try:
            yield session
        except BaseException:
            await session.rollback()
            raise
        else:
            await session.commit()
