from typing import Annotated, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.rate_limiter import RateLimiter
from app.crud.crud_webhook import webhook_crud
from app.models.api_key import APIKey
from app.models.user import User
from app.schemas.webhook import (
    WebhookDeliveryLogRead,
    WebhookDispatchEvent,
    WebhookEndpointCreate,
    WebhookEndpointRead,
)
from app.worker.tasks import send_webhook_event

from fastapi import Request
from pydantic import BaseModel
from app.core.verifier import WebhookVerificationError, verifier

from app.schemas.webhook import WebhookStatsResponse

router = APIRouter()


@router.post(
    "/endpoints",
    response_model=WebhookEndpointRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a destination webhook URL",
)
async def create_webhook_endpoint(
    endpoint_in: WebhookEndpointCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return await webhook_crud.create_endpoint_for_user(
        db, obj_in=endpoint_in, user_id=current_user.id
    )


@router.get(
    "/endpoints",
    response_model=List[WebhookEndpointRead],
    summary="List registered webhook endpoints",
)
async def list_webhook_endpoints(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return await webhook_crud.get_endpoints_by_user(db, user_id=current_user.id)


@router.get(
    "/endpoints/{endpoint_id}/logs",
    response_model=List[WebhookDeliveryLogRead],
    summary="List delivery logs for an endpoint",
)
async def get_endpoint_logs(
    endpoint_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    endpoint = await webhook_crud.get(db, id=endpoint_id)
    if not endpoint or endpoint.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook endpoint not found.",
        )
    return await webhook_crud.get_delivery_logs_by_endpoint(
        db, endpoint_id=endpoint_id, skip=skip, limit=limit
    )


@router.post(
    "/dispatch",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Dispatch a webhook event to all active endpoints",
)
async def dispatch_webhook_event(
    event_in: WebhookDispatchEvent,
    db: Annotated[AsyncSession, Depends(get_db)],
    api_key: Annotated[APIKey, Depends(RateLimiter(cost=1))],
):
    endpoints = await webhook_crud.get_endpoints_by_user(db, user_id=api_key.user_id)
    if not endpoints:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active destination webhook endpoints found for this account.",
        )

    dispatched_task_ids = []

    for endpoint in endpoints:
        log_entry = await webhook_crud.create_delivery_log(
            db, endpoint_id=endpoint.id, event_in=event_in
        )
        task = send_webhook_event.delay(str(log_entry.id))
        dispatched_task_ids.append(task.id)

    return {
        "status": "queued",
        "event_type": event_in.event_type,
        "endpoints_targeted": len(endpoints),
        "task_ids": dispatched_task_ids,
    }

class VerifyTestRequest(BaseModel):
    payload: dict
    signature_header: str
    secret_token: str


@router.post(
    "/verify-test",
    summary="Utility endpoint to verify webhook HMAC signatures",
)
async def test_verify_signature(data: VerifyTestRequest):
    """
    Subscribers can use this endpoint to test their signature generation and verification.
    """
    import json
    payload_str = json.dumps(data.payload, separators=(",", ":"))

    try:
        is_valid = verifier.verify(
            raw_body=payload_str,
            header_value=data.signature_header,
            secret_token=data.secret_token,
        )
        return {"valid": is_valid, "message": "Signature verified successfully."}
    except WebhookVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Verification failed: {str(exc)}",
        )

@router.post(
    "/logs/{log_id}/retry",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Manually replay a webhook delivery",
)
async def retry_webhook_delivery(
    log_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Manually re-enqueues a webhook delivery log into Celery.
    Can be used for permanently failed or pending dispatches.
    """
    # 1. Verify ownership
    log_entry = await webhook_crud.get_log_by_user(
        db, log_id=log_id, user_id=current_user.id
    )
    if not log_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery log not found or does not belong to the user.",
        )

    # 2. Reset log status in database
    await webhook_crud.reset_delivery_log_for_retry(db, log=log_entry)

    # 3. Re-enqueue the Celery background task
    task = send_webhook_event.delay(str(log_entry.id))

    return {
        "status": "requeued",
        "log_id": str(log_entry.id),
        "task_id": task.id,
    }

@router.get(
    "/stats",
    response_model=WebhookStatsResponse,
    summary="Get webhook delivery health metrics & analytics",
)
async def get_webhook_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    hours: int = Query(24, ge=1, le=720, description="Rolling metrics window in hours (default 24h)"),
):
    """
    Returns aggregated delivery metrics, success rates, average latency,
    and HTTP status code breakdowns for the authenticated user.
    """
    return await webhook_crud.get_user_stats(db, user_id=current_user.id, window_hours=hours)