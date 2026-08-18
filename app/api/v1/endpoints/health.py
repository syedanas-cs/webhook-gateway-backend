import time
from typing import Annotated
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
import redis.asyncio as redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis

router = APIRouter()


@router.get(
    "/health",
    summary="Comprehensive system healthcheck",
    status_code=status.HTTP_200_OK,
)
async def health_check(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
):
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "services": {
            "database": "unknown",
            "redis": "unknown",
        },
    }

    # 1. Probe Database
    try:
        await db.execute(text("SELECT 1"))
        health_status["services"]["database"] = "reachable"
    except Exception as exc:
        health_status["services"]["database"] = f"unreachable: {str(exc)}"
        health_status["status"] = "unhealthy"

    # 2. Probe Redis
    try:
        pong = await redis_client.ping()
        health_status["services"]["redis"] = "reachable" if pong else "unreachable"
    except Exception as exc:
        health_status["services"]["redis"] = f"unreachable: {str(exc)}"
        health_status["status"] = "unhealthy"

    status_code = (
        status.HTTP_200_OK
        if health_status["status"] == "healthy"
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return JSONResponse(status_code=status_code, content=health_status)