"""Periodic cleanup of expired security state.

Runs inside each API process. The deletes are idempotent, so several replicas running
them concurrently is harmless. Expired rows are kept for a grace period so recent
activity remains visible on the security screens.
"""

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import delete, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.auth.models import UserSession
from app.modules.auth.service import utcnow
from app.modules.organizations.models import Invitation
from app.security.models import RateLimitBucket

logger = logging.getLogger(__name__)

PRUNE_INTERVAL = timedelta(hours=1)
SESSION_RETENTION = timedelta(days=30)
INVITATION_RETENTION = timedelta(days=30)
RATE_LIMIT_RETENTION = timedelta(days=1)


async def prune_expired_state(db: AsyncSession) -> dict[str, int]:
    now = utcnow()
    sessions = await db.execute(
        delete(UserSession).where(
            or_(
                UserSession.expires_at < now - SESSION_RETENTION,
                UserSession.revoked_at < now - SESSION_RETENTION,
            )
        )
    )
    invitations = await db.execute(
        delete(Invitation).where(
            or_(
                Invitation.expires_at < now - INVITATION_RETENTION,
                Invitation.revoked_at < now - INVITATION_RETENTION,
                Invitation.accepted_at < now - INVITATION_RETENTION,
            )
        )
    )
    buckets = await db.execute(
        delete(RateLimitBucket).where(
            RateLimitBucket.window_started_at < now - RATE_LIMIT_RETENTION
        )
    )
    return {
        "sessions": sessions.rowcount,  # type: ignore[attr-defined]
        "invitations": invitations.rowcount,  # type: ignore[attr-defined]
        "rate_limit_buckets": buckets.rowcount,  # type: ignore[attr-defined]
    }


async def run_forever(session_factory: async_sessionmaker[AsyncSession]) -> None:
    while True:
        try:
            async with session_factory.begin() as db:
                removed = await prune_expired_state(db)
            logger.info("expired_state_pruned", extra=removed)
        except SQLAlchemyError, OSError, TimeoutError:
            # Transient database trouble: try again next cycle.
            logger.exception("expired_state_prune_failed")
        await asyncio.sleep(PRUNE_INTERVAL.total_seconds())


def report_crash(task: asyncio.Task[None]) -> None:
    """Done-callback: a maintenance loop that dies for an unexpected reason must be loud."""
    if not task.cancelled() and (error := task.exception()) is not None:
        logger.critical("maintenance_loop_crashed", exc_info=error)
