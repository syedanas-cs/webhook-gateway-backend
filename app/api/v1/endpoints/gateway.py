from typing import Annotated, Any, Dict
from fastapi import APIRouter, Depends, status
from app.core.rate_limiter import RateLimiter
from app.models.api_key import APIKey

router = APIRouter()


@router.post(
    "/dispatch",
    status_code=status.HTTP_200_OK,
    summary="Rate-limited gateway entrypoint",
)
async def dispatch_gateway_message(
    payload: Dict[str, Any],
    api_key: Annotated[APIKey, Depends(RateLimiter(cost=1))],
):
    """
    Protected webhook dispatch endpoint throttled by user plan tier via Redis.
    """
    return {
        "status": "accepted",
        "authenticated_key_id": str(api_key.id),
        "received_payload": payload,
    }