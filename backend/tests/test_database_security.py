"""Database-level guarantees, exercised as the real runtime role."""

import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.db.rls import tenant_isolation_sql
from app.db.session import bind_tenant
from app.maintenance import SESSION_RETENTION, prune_expired_state
from app.modules.auth.service import utcnow
from tests.helpers import Browser

PROBE = "rls_probe"


@pytest.fixture
def factory(app: FastAPI) -> async_sessionmaker[AsyncSession]:
    session_factory: async_sessionmaker[AsyncSession] = app.state.session_factory
    return session_factory


@pytest.fixture
async def tenant_table(admin_engine: AsyncEngine) -> AsyncIterator[str]:
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                f"CREATE TABLE {PROBE} (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, "
                "organization_id uuid NOT NULL, label text NOT NULL)"
            )
        )
        for statement in tenant_isolation_sql(PROBE):
            await conn.execute(text(statement))
    yield PROBE
    async with admin_engine.begin() as conn:
        await conn.execute(text(f"DROP TABLE {PROBE}"))


async def _labels(session: AsyncSession) -> list[str]:
    return list((await session.scalars(text(f"SELECT label FROM {PROBE} ORDER BY id"))).all())


async def test_row_level_security_isolates_tenants(
    factory: async_sessionmaker[AsyncSession], tenant_table: str
) -> None:
    farm_a, farm_b = uuid.uuid7(), uuid.uuid7()
    insert = text(f"INSERT INTO {tenant_table} (organization_id, label) VALUES (:org, :label)")

    for org, label in ((farm_a, "trator-a"), (farm_b, "colheitadeira-b")):
        async with factory() as session:
            await bind_tenant(session, org)
            await session.execute(insert, {"org": org, "label": label})
            await session.commit()

    async with factory() as session:
        await bind_tenant(session, farm_a)
        assert await _labels(session) == ["trator-a"]
        await session.commit()
        # The tenant is re-applied on every new transaction of the same session.
        assert await _labels(session) == ["trator-a"]

    async with factory() as session:
        await bind_tenant(session, farm_b)
        assert await _labels(session) == ["colheitadeira-b"]

    async with factory() as session:
        # No tenant bound: fail closed.
        assert await _labels(session) == []

    async with factory() as session:
        await bind_tenant(session, farm_a)
        with pytest.raises(DBAPIError, match="row-level security"):
            await session.execute(insert, {"org": farm_b, "label": "intruso"})


async def test_runtime_role_cannot_rewrite_audit_trail(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    for statement in ("UPDATE audit_events SET action = 'x'", "DELETE FROM audit_events"):
        async with factory() as session:
            with pytest.raises(DBAPIError, match="permission denied"):
                await session.execute(text(statement))


async def test_runtime_role_cannot_change_schema(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    async with factory() as session:
        with pytest.raises(DBAPIError, match="permission denied"):
            await session.execute(text("CREATE TABLE intruder (id int)"))


async def test_session_tokens_are_stored_hashed(
    browser: Browser, admin_engine: AsyncEngine
) -> None:
    await browser.register()
    raw_token = browser.http.cookies["georgos_session"]
    async with admin_engine.connect() as conn:
        stored = (await conn.execute(text("SELECT token_hash FROM user_sessions"))).scalar_one()
    assert raw_token.encode() not in bytes(stored)
    assert len(stored) == 32


async def test_prune_removes_only_long_expired_state(
    browser: Browser, admin_engine: AsyncEngine, factory: async_sessionmaker[AsyncSession]
) -> None:
    await browser.register()
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO user_sessions (token_hash, user_id, organization_id, expires_at) "
                "SELECT decode(repeat('ab', 32), 'hex'), user_id, organization_id, :expired "
                "FROM memberships LIMIT 1"
            ),
            {"expired": utcnow() - SESSION_RETENTION - timedelta(days=1)},
        )

    async with factory.begin() as session:
        removed = await prune_expired_state(session)

    assert removed["sessions"] == 1
    assert (await browser.get("/auth/session")).status_code == 200
