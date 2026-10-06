import logging

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

router = APIRouter(prefix="/health", tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/live")
async def live() -> dict[str, str]:
    """The process is up. Used by orchestrators to decide on restarts."""
    return {"status": "ok"}


@router.get("/ready", response_model=None)
async def ready(request: Request) -> dict[str, str] | JSONResponse:
    """The process can serve traffic: the database answers and migrations have run."""
    engine: AsyncEngine = request.app.state.engine
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1 FROM alembic_version"))
    except SQLAlchemyError, OSError, TimeoutError:
        logger.warning("readiness_check_failed", exc_info=True)
        return JSONResponse(
            {"status": "unavailable", "database": "unreachable"},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return {"status": "ok", "database": "ok"}
