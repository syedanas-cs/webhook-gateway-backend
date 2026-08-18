import enum
import uuid
from typing import TYPE_CHECKING, Any, Dict, List
from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampUUIDMixin

if TYPE_CHECKING:
    from app.models.user import User

class DeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"

class WebhookEndpoint(Base, TimestampUUIDMixin):
    __tablename__ = "webhook_endpoints"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    target_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    secret_token: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Signing secret for HMAC-SHA256 headers"
    )
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="webhook_endpoints")
    delivery_logs: Mapped[List["WebhookDeliveryLog"]] = relationship(
        "WebhookDeliveryLog", back_populates="endpoint", cascade="all, delete-orphan"
    )

class WebhookDeliveryLog(Base, TimestampUUIDMixin):
    __tablename__ = "webhook_delivery_logs"

    endpoint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("webhook_endpoints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    
    # Execution & Response Metadata
    status: Mapped[DeliveryStatus] = mapped_column(
        Enum(DeliveryStatus, name="delivery_status_enum", native_enum=True),
        default=DeliveryStatus.PENDING,
        index=True,
        nullable=False,
    )
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    endpoint: Mapped["WebhookEndpoint"] = relationship(
        "WebhookEndpoint", back_populates="delivery_logs"
    )