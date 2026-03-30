from __future__ import annotations

import json
import logging

import aioboto3

from app.config import Settings
from app.models.schemas import QueueMessage
from app.utils.exceptions import QueuePublishError

logger = logging.getLogger(__name__)


class SQSPublisher:
    """Publishes processing messages to SQS, or falls back to HTTP webhook."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._session = aioboto3.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )

    async def publish(self, message: QueueMessage) -> str:
        queue_url = self._settings.sqs_queue_url
        if queue_url:
            return await self._publish_sqs(message, queue_url)

        webhook_url = self._settings.processing_webhook_url
        if webhook_url:
            return await self._publish_webhook(message, webhook_url)

        logger.warning("Neither SQS nor webhook configured – skipping publish")
        return "no-op"

    async def _publish_sqs(self, message: QueueMessage, queue_url: str) -> str:
        body = json.dumps(message.model_dump(), default=str)
        logger.info("Publishing ingestion_id=%s to SQS", message.ingestion_id)

        try:
            async with self._session.client(
                "sqs", endpoint_url=self._settings.sqs_endpoint_url
            ) as sqs:
                resp = await sqs.send_message(
                    QueueUrl=queue_url,
                    MessageBody=body,
                    MessageAttributes={
                        "file_category": {
                            "DataType": "String",
                            "StringValue": message.file_category.value,
                        },
                        "ingestion_id": {
                            "DataType": "String",
                            "StringValue": message.ingestion_id,
                        },
                    },
                )
                message_id = resp["MessageId"]
                logger.info("SQS message sent: MessageId=%s", message_id)
                return message_id

        except Exception as exc:
            logger.exception("Failed to publish to SQS")
            raise QueuePublishError(
                f"Failed to publish message for '{message.ingestion_id}': {exc}"
            ) from exc

    async def _publish_webhook(self, message: QueueMessage, webhook_url: str) -> str:
        import httpx

        body = json.loads(json.dumps(message.model_dump(), default=str))
        logger.info("POSTing ingestion_id=%s to webhook %s", message.ingestion_id, webhook_url)

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(webhook_url, json=body)
                resp.raise_for_status()
                data = resp.json()
                logger.info(
                    "Webhook accepted ingestion_id=%s (status=%s)",
                    message.ingestion_id, data.get("status", "unknown"),
                )
                return f"webhook-{message.ingestion_id}"
        except Exception as exc:
            logger.exception("Webhook POST failed for ingestion_id=%s", message.ingestion_id)
            raise QueuePublishError(
                f"Webhook failed for '{message.ingestion_id}': {exc}"
            ) from exc
