import secrets
from typing import Sequence
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.webhook import DeliveryStatus, WebhookDeliveryLog, WebhookEndpoint
from app.schemas.webhook import WebhookDispatchEvent, WebhookEndpointCreate


class CRUDWebhook(CRUDBase[WebhookEndpoint, WebhookEndpointCreate, WebhookEndpointCreate]):
    async def create_endpoint_for_user(
        self, db: AsyncSession, *, obj_in: WebhookEndpointCreate, user_id: UUID
    ) -> WebhookEndpoint:
        secret = obj_in.secret_token or secrets.token_hex(32)

        db_obj = WebhookEndpoint(
            user_id=user_id,
            target_url=str(obj_in.target_url),
            description=obj_in.description,
            secret_token=secret,
            is_active=obj_in.is_active,
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def get_endpoints_by_user(
        self, db: AsyncSession, *, user_id: UUID
    ) -> Sequence[WebhookEndpoint]:
        result = await db.execute(
            select(WebhookEndpoint).where(
                WebhookEndpoint.user_id == user_id,
                WebhookEndpoint.is_active == True,
            )
        )
        return result.scalars().all()

    async def create_delivery_log(
        self,
        db: AsyncSession,
        *,
        endpoint_id: UUID,
        event_in: WebhookDispatchEvent,
    ) -> WebhookDeliveryLog:
        db_log = WebhookDeliveryLog(
            endpoint_id=endpoint_id,
            event_type=event_in.event_type,
            payload=event_in.payload,
            status=DeliveryStatus.PENDING,
            attempt_count=0,
        )
        db.add(db_log)
        await db.commit()
        await db.refresh(db_log)
        return db_log

    async def get_delivery_logs_by_endpoint(
        self, db: AsyncSession, *, endpoint_id: UUID, skip: int = 0, limit: int = 50
    ) -> Sequence[WebhookDeliveryLog]:
        result = await db.execute(
            select(WebhookDeliveryLog)
            .where(WebhookDeliveryLog.endpoint_id == endpoint_id)
            .order_by(WebhookDeliveryLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()


webhook_crud = CRUDWebhook(WebhookEndpoint)