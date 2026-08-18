import enum
from typing import TYPE_CHECKING, List
from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampUUIDMixin

if TYPE_CHECKING:
    from app.models.api_key import APIKey
    from app.models.webhook import WebhookEndpoint

class PlanTier(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"

class User(Base, TimestampUUIDMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    plan_tier: Mapped[PlanTier] = mapped_column(Enum(PlanTier, name="plan_tier_enum", native_enum=True), default=PlanTier.FREE, nullable=False)

    # Relationships
    api_keys: Mapped[List["APIKey"]] = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    webhook_endpoints: Mapped[List["WebhookEndpoint"]] = relationship("WebhookEndpoint", back_populates="user", cascade="all, delete-orphan")