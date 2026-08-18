from datetime import datetime
from typing import Any, Dict
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from app.models.webhook import DeliveryStatus


# --- Webhook Endpoint Registration ---
class WebhookEndpointBase(BaseModel):
    target_url: HttpUrl = Field(description="Destination HTTP/HTTPS endpoint")
    description: str | None = Field(default=None, max_length=255)
    is_active: bool = True


class WebhookEndpointCreate(WebhookEndpointBase):
    secret_token: str | None = Field(
        default=None,
        min_length=16,
        max_length=255,
        description="Optional custom secret; if omitted, a secure token will be auto-generated.",
    )


class WebhookEndpointRead(WebhookEndpointBase):
    id: UUID
    user_id: UUID
    secret_token: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Webhook Dispatch & Delivery Logs ---
class WebhookDispatchEvent(BaseModel):
    event_type: str = Field(min_length=1, max_length=100, examples=["order.completed"])
    payload: Dict[str, Any] = Field(
        description="JSON serializable dictionary to send to subscriber endpoint"
    )


class WebhookDeliveryLogRead(BaseModel):
    id: UUID
    endpoint_id: UUID
    event_type: str
    payload: Dict[str, Any]
    status: DeliveryStatus
    status_code: int | None
    response_body: str | None
    response_time_ms: int | None
    attempt_count: int
    error_message: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class StatusBreakdown(BaseModel):
    success: int = 0
    failed: int = 0
    pending: int = 0
    retrying: int = 0


class StatusCodeBreakdown(BaseModel):
    http_2xx: int = 0
    http_4xx: int = 0
    http_5xx: int = 0
    other: int = 0


class WebhookStatsResponse(BaseModel):
    total_deliveries: int
    success_rate_percentage: float
    average_response_time_ms: float
    status_breakdown: StatusBreakdown
    status_code_breakdown: StatusCodeBreakdown
    window_hours: int