import asyncio
import hashlib
import hmac
import json
import time
from uuid import UUID
import httpx
from celery import Task
from celery.utils.log import get_task_logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models.webhook import DeliveryStatus, WebhookDeliveryLog, WebhookEndpoint
from app.worker.celery_app import celery_app

logger = get_task_logger(__name__)

# Dedicated engine for Celery workers using NullPool to prevent event loop connection conflicts
worker_engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    poolclass=NullPool,
    echo=False,
)

WorkerSessionLocal = async_sessionmaker(
    bind=worker_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def generate_signature(secret: str, timestamp: str, payload_str: str) -> str:
    """Generates an HMAC-SHA256 signature formatted as t={timestamp},v1={hex_digest}."""
    signed_payload = f"t={timestamp}.{payload_str}".encode("utf-8")
    signature = hmac.new(
        key=secret.encode("utf-8"),
        msg=signed_payload,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return f"t={timestamp},v1={signature}"


async def _execute_webhook_delivery(task_instance: Task, log_id: UUID) -> None:
    async with WorkerSessionLocal() as db:
        stmt = (
            select(WebhookDeliveryLog, WebhookEndpoint)
            .join(WebhookEndpoint, WebhookDeliveryLog.endpoint_id == WebhookEndpoint.id)
            .where(WebhookDeliveryLog.id == log_id)
        )
        result = await db.execute(stmt)
        record = result.first()

        if not record:
            logger.error(f"Delivery log {log_id} not found.")
            return

        delivery_log, endpoint = record

        if not endpoint.is_active:
            delivery_log.status = DeliveryStatus.FAILED
            delivery_log.error_message = "Webhook endpoint is disabled"
            await db.commit()
            return

        payload_str = json.dumps(delivery_log.payload, separators=(",", ":"))
        timestamp = str(int(time.time()))
        signature_header = generate_signature(endpoint.secret_token, timestamp, payload_str)

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "WebhookGateway-DeliveryEngine/1.0",
            "X-Webhook-ID": str(delivery_log.id),
            "X-Webhook-Event": delivery_log.event_type,
            "X-Webhook-Timestamp": timestamp,
            "X-Webhook-Signature": signature_header,
        }

        delivery_log.attempt_count = task_instance.request.retries + 1
        start_time = time.perf_counter()

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    endpoint.target_url,
                    content=payload_str,
                    headers=headers,
                )

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            delivery_log.response_time_ms = elapsed_ms
            delivery_log.status_code = response.status_code
            delivery_log.response_body = response.text[:2000]

            if 200 <= response.status_code < 300:
                delivery_log.status = DeliveryStatus.SUCCESS
                delivery_log.error_message = None
                await db.commit()
                return
            else:
                raise httpx.HTTPStatusError(
                    f"Non-2xx HTTP status received: {response.status_code}",
                    request=response.request,
                    response=response,
                )

        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            delivery_log.response_time_ms = elapsed_ms
            delivery_log.error_message = str(exc)[:1000]

            if task_instance.request.retries < task_instance.max_retries:
                delivery_log.status = DeliveryStatus.RETRYING
                await db.commit()

                countdown = 2 ** (task_instance.request.retries + 1)
                logger.warning(
                    f"Retrying delivery {log_id} in {countdown}s due to error: {exc}"
                )
                raise task_instance.retry(exc=exc, countdown=countdown)
            else:
                delivery_log.status = DeliveryStatus.FAILED
                await db.commit()
                logger.error(f"Delivery {log_id} exhausted all retries. Marked as failed.")


@celery_app.task(bind=True, max_retries=5)
def send_webhook_event(self: Task, delivery_log_id: str) -> None:
    """Celery task entry point to deliver webhook payloads asynchronously."""
    asyncio.run(_execute_webhook_delivery(self, UUID(delivery_log_id)))