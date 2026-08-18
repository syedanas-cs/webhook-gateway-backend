from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class APIKeyBase(BaseModel):
    name: str = Field(min_length=1, max_length=100, examples=["Production Server Key"])
    rate_limit_override: int | None = Field(
        default=None, ge=1, le=100000, description="Custom req/min override"
    )
    expires_at: datetime | None = None


class APIKeyCreate(APIKeyBase):
    pass


class APIKeyRead(APIKeyBase):
    id: UUID
    user_id: UUID
    prefix: str
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class APIKeyCreateResponse(APIKeyRead):
    # Plaintext key is returned ONLY once when created
    raw_api_key: str = Field(
        description="Full plaintext API key. Store this securely; it will not be displayed again."
    )