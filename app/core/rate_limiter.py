import time
from typing import Annotated
from fastapi import Depends, HTTPException, Header, status
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.crud.crud_api_key import api_key_crud
from app.crud.crud_user import user_crud
from app.models.api_key import APIKey
from app.models.user import PlanTier

# Atomic Redis Lua script for Token Bucket
TOKEN_BUCKET_LUA_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local fill_rate = tonumber(ARGV[2])
local cost = tonumber(ARGV[3])
local now = tonumber(ARGV[4])

-- Retrieve current state [tokens, last_updated]
local data = redis.call("HMGET", key, "tokens", "last_updated")
local tokens = tonumber(data[1])
local last_updated = tonumber(data[2])

if tokens == nil then
    tokens = capacity
    last_updated = now
else
    local delta = math.max(0, now - last_updated)
    local tokens_to_add = delta * fill_rate
    tokens = math.min(capacity, tokens + tokens_to_add)
    last_updated = now
end

if tokens >= cost then
    tokens = tokens - cost
    redis.call("HMSET", key, "tokens", tokens, "last_updated", last_updated)
    -- Set TTL to ensure unused keys expire (e.g. 1 hour)
    redis.call("EXPIRE", key, 3600)
    return {1, math.floor(tokens), 0}
else
    redis.call("HMSET", key, "tokens", tokens, "last_updated", last_updated)
    redis.call("EXPIRE", key, 3600)
    local retry_after = math.ceil((cost - tokens) / fill_rate)
    return {0, math.floor(tokens), retry_after}
end
"""

# Default capacities (burst limit) and refill rates (requests per second)
PLAN_RATE_LIMITS: dict[PlanTier, dict[str, float]] = {
    PlanTier.FREE: {"capacity": 60, "fill_rate": 1.0},        # 60 req/min
    PlanTier.PRO: {"capacity": 1000, "fill_rate": 16.67},     # 1,000 req/min (~16.67/s)
    PlanTier.ENTERPRISE: {"capacity": 10000, "fill_rate": 166.67}, # 10,000 req/min
}


class RateLimiter:
    def __init__(self, cost: int = 1):
        self.cost = cost

    async def __call__(
        self,
        db: Annotated[AsyncSession, Depends(get_db)],
        redis_client: Annotated[redis.Redis, Depends(get_redis)],
        x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    ) -> APIKey:
        if not x_api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing 'X-API-Key' header",
            )

        api_key = await api_key_crud.get_by_raw_key(db, raw_key=x_api_key)
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked API Key",
            )

        # Determine rate limits based on overrides or user plan tier
        if api_key.rate_limit_override:
            capacity = api_key.rate_limit_override
            fill_rate = capacity / 60.0
        else:
            user = await user_crud.get(db, id=api_key.user_id)
            plan = user.plan_tier if user else PlanTier.FREE
            limits = PLAN_RATE_LIMITS.get(plan, PLAN_RATE_LIMITS[PlanTier.FREE])
            capacity = limits["capacity"]
            fill_rate = limits["fill_rate"]

        rate_limit_key = f"rate_limit:key:{api_key.id}"
        now = time.time()

        # Execute Lua script atomically
        result = await redis_client.eval(
            TOKEN_BUCKET_LUA_SCRIPT,
            1,
            rate_limit_key,
            capacity,
            fill_rate,
            self.cost,
            now,
        )

        allowed, remaining_tokens, retry_after = result[0], result[1], result[2]

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Try again later.",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(int(capacity)),
                    "X-RateLimit-Remaining": "0",
                },
            )

        return api_key