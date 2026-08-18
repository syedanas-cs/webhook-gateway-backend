import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampUUIDMixin

if TYPE_CHECKING:
    from app.models.user import User

class APIKey(Base, TimestampUUIDMixin):
    __tablename__ = "api_keys"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    hashed_key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rate_limit_override: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Custom req/min override if not using plan default")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="api_keys")