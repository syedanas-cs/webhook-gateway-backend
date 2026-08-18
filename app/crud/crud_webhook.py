import secrets
from typing import Sequence
from uuid import UUID
from celery import result
from sqlalchemy import log, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.webhook import DeliveryStatus, WebhookDeliveryLog, WebhookEndpoint
from app.schemas.webhook import WebhookDispatchEvent, WebhookEndpointCreate

from datetime import datetime, timedelta, timezone
from sqlalchemy import case, func


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

    async def get_log_by_user(self, db: AsyncSession, *, log_id: UUID, user_id: UUID) -> WebhookDeliveryLog | None:
        """Fetches a delivery log ensuring the associated endpoint belongs to the user."""
        stmt = (select(WebhookDeliveryLog)
        .join(WebhookEndpoint, WebhookDeliveryLog.endpoint_id == WebhookEndpoint.id)
        .where(
            WebhookDeliveryLog.id == log_id,
            WebhookEndpoint.user_id == user_id,
            )
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def reset_delivery_log_for_retry(self, db: AsyncSession, *, log: WebhookDeliveryLog) -> WebhookDeliveryLog:
        """Resets delivery log status and error message to PENDING for re-dispatch."""
        log.status = DeliveryStatus.PENDING
        log.error_message = None
        log.attempt_count = 0
        db.add(log)
        await db.commit()
        await db.refresh(log)
        return log

    async def get_user_stats(self,db: AsyncSession,*,user_id: UUID,window_hours: int = 24,) -> dict:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=window_hours)

        stmt = (
            select(
                func.count(WebhookDeliveryLog.id).label("total_deliveries"),
                func.coalesce(
                    func.avg(WebhookDeliveryLog.response_time_ms).filter(
                        WebhookDeliveryLog.response_time_ms.is_not(None)
                    ),
                    0.0,
                ).label("avg_response_time"),
                # Status Counts
                func.count(
                    case((WebhookDeliveryLog.status == DeliveryStatus.SUCCESS, 1))
                ).label("count_success"),
                func.count(
                    case((WebhookDeliveryLog.status == DeliveryStatus.FAILED, 1))
                ).label("count_failed"),
                func.count(
                    case((WebhookDeliveryLog.status == DeliveryStatus.PENDING, 1))
                ).label("count_pending"),
                func.count(
                    case((WebhookDeliveryLog.status == DeliveryStatus.RETRYING, 1))
                ).label("count_retrying"),
                # HTTP Code Breakdowns
                func.count(
                    case(
                        (
                            (WebhookDeliveryLog.status_code >= 200)
                            & (WebhookDeliveryLog.status_code < 300),
                            1,
                        )
                    )
                ).label("http_2xx"),
                func.count(
                    case(
                        (
                            (WebhookDeliveryLog.status_code >= 400)
                            & (WebhookDeliveryLog.status_code < 500),
                            1,
                        )
                    )
                ).label("http_4xx"),
                func.count(
                    case(
                        (
                            (WebhookDeliveryLog.status_code >= 500)
                            & (WebhookDeliveryLog.status_code < 600),
                            1,
                        )
                    )
                ).label("http_5xx"),
                func.count(
                    case(
                        (
                            (WebhookDeliveryLog.status_code.is_not(None))
                            & (WebhookDeliveryLog.status_code < 200)
                            | (WebhookDeliveryLog.status_code >= 600),
                            1,
                        )
                    )
                ).label("http_other"),
            )
            .join(WebhookEndpoint, WebhookDeliveryLog.endpoint_id == WebhookEndpoint.id)
            .where(
                WebhookEndpoint.user_id == user_id,
                WebhookDeliveryLog.created_at >= cutoff_time,
            )
        )

        result = await db.execute(stmt)
        row = result.mappings().first()

        total = row["total_deliveries"] if row else 0
        success = row["count_success"] if row else 0
        success_rate = (success / total * 100.0) if total > 0 else 0.0

        return {
            "total_deliveries": total,
            "success_rate_percentage": round(success_rate, 2),
            "average_response_time_ms": round(float(row["avg_response_time"] or 0.0), 2)
            if row
            else 0.0,
            "status_breakdown": {
                "success": success,
                "failed": row["count_failed"] if row else 0,
                "pending": row["count_pending"] if row else 0,
                "retrying": row["count_retrying"] if row else 0,
            },
            "status_code_breakdown": {
                "http_2xx": row["http_2xx"] if row else 0,
                "http_4xx": row["http_4xx"] if row else 0,
                "http_5xx": row["http_5xx"] if row else 0,
                "other": row["http_other"] if row else 0,
            },
            "window_hours": window_hours,
        }


webhook_crud = CRUDWebhook(WebhookEndpoint)