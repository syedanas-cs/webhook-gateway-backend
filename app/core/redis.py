from typing import AsyncGenerator
import redis.asyncio as redis
from app.core.config import settings

# Global async Redis connection pool
redis_pool = redis.ConnectionPool.from_url(
    str(settings.REDIS_URL),
    max_connections=20,
    decode_responses=True,
)


async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    """Yields an async Redis client from the connection pool."""
    client = redis.Redis(connection_pool=redis_pool)
    try:
        yield client
    finally:
        await client.aclose()