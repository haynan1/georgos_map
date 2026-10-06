"""Fixed-window rate limiting backed by PostgreSQL.

Postgres instead of process memory so limits hold across API replicas and restarts, and
instead of Redis because one more stateful service is not justified at this scale: a
single-row upsert per attempt is cheap. Each check runs in its own short transaction so
an attempt is recorded even when the surrounding request fails and rolls back.
"""

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import RateLimited


@dataclass(frozen=True, slots=True)
class Limit:
    scope: str
    max_hits: int
    window: timedelta


LOGIN_PER_IP = Limit("login:ip", max_hits=30, window=timedelta(minutes=15))
LOGIN_FAILURES_PER_ACCOUNT = Limit("login:account", max_hits=8, window=timedelta(minutes=15))
REGISTER_PER_IP = Limit("register:ip", max_hits=5, window=timedelta(hours=1))
INVITATION_PER_IP = Limit("invitation:ip", max_hits=30, window=timedelta(minutes=15))
PASSWORD_CHANGE_PER_USER = Limit("password:user", max_hits=8, window=timedelta(minutes=15))

_HIT = text(
    """
    INSERT INTO rate_limit_buckets AS b (key, window_started_at, hits)
    VALUES (:key, now(), 1)
    ON CONFLICT (key) DO UPDATE SET
        hits = CASE
            WHEN b.window_started_at <= now() - CAST(:window AS interval) THEN 1
            ELSE b.hits + 1
        END,
        window_started_at = CASE
            WHEN b.window_started_at <= now() - CAST(:window AS interval) THEN now()
            ELSE b.window_started_at
        END
    RETURNING
        hits,
        EXTRACT(EPOCH FROM (b.window_started_at + CAST(:window AS interval) - now()))::int
    """
)
_CLEAR = text("DELETE FROM rate_limit_buckets WHERE key = :key")


class RateLimiter:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = session_factory

    @staticmethod
    def _key(limit: Limit, identity: str) -> str:
        return f"{limit.scope}:{identity}"

    async def hit(self, limit: Limit, identity: str) -> None:
        """Count one attempt; raise once the window's budget is exhausted."""
        async with self._factory.begin() as session:
            row = (
                await session.execute(
                    _HIT, {"key": self._key(limit, identity), "window": limit.window}
                )
            ).one()
        hits, retry_after = row
        if hits > limit.max_hits:
            raise RateLimited(retry_after)

    async def clear(self, limit: Limit, identity: str) -> None:
        async with self._factory.begin() as session:
            await session.execute(_CLEAR, {"key": self._key(limit, identity)})
