from __future__ import annotations

import json
import logging

import aioboto3

from app.config import Settings
from app.models.schemas import QueueMessage
from app.utils.exceptions import QueuePublishError

logger = logging.getLogger(__name__)


class SQSPublisher:
    """Publishes processing messages to an AWS SQS queue."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._session = aioboto3.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )

    async def publish(self, message: QueueMessage) -> str:
        """
        Publish a QueueMessage to SQS.

        Returns the SQS MessageId on success.
        """
        queue_url = self._settings.sqs_queue_url
        if not queue_url:
            logger.warning("SQS queue URL not configured – skipping publish")
            return "no-op"

        body = json.dumps(message.model_dump(), default=str)
        logger.info(
            "Publishing message for ingestion_id=%s to SQS", message.ingestion_id
        )

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
