from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

import aioboto3

from app.models.enums import FileCategory, ProcessingPipeline
from app.models.schemas import QueueMessage

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


class SQSConsumer:
    """Long-polling SQS consumer with graceful shutdown support."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._session = aioboto3.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    async def poll_messages(self) -> list[tuple[QueueMessage, str]]:
        """
        Single poll cycle. Returns list of (parsed_message, receipt_handle) tuples.
        """
        queue_url = self._settings.sqs_queue_url
        if not queue_url:
            logger.warning("SQS queue URL not configured – sleeping")
            await asyncio.sleep(5)
            return []

        try:
            async with self._session.client(
                "sqs", endpoint_url=self._settings.sqs_endpoint_url
            ) as sqs:
                resp = await sqs.receive_message(
                    QueueUrl=queue_url,
                    MaxNumberOfMessages=self._settings.sqs_max_messages,
                    WaitTimeSeconds=self._settings.sqs_wait_time_seconds,
                    VisibilityTimeout=self._settings.sqs_visibility_timeout,
                    MessageAttributeNames=["All"],
                )

            messages = resp.get("Messages", [])
            if not messages:
                return []

            logger.info("Received %d message(s) from SQS", len(messages))
            results: list[tuple[QueueMessage, str]] = []

            for msg in messages:
                try:
                    parsed = self._parse_message(msg)
                    results.append((parsed, msg["ReceiptHandle"]))
                except Exception:
                    logger.exception("Failed to parse SQS message: %s", msg.get("MessageId"))

            return results

        except Exception:
            logger.exception("SQS poll error")
            await asyncio.sleep(2)
            return []

    async def delete_message(self, receipt_handle: str) -> None:
        queue_url = self._settings.sqs_queue_url
        if not queue_url:
            return
        try:
            async with self._session.client(
                "sqs", endpoint_url=self._settings.sqs_endpoint_url
            ) as sqs:
                await sqs.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=receipt_handle,
                )
        except Exception:
            logger.exception("Failed to delete SQS message")

    async def change_visibility(self, receipt_handle: str, timeout: int) -> None:
        queue_url = self._settings.sqs_queue_url
        if not queue_url:
            return
        try:
            async with self._session.client(
                "sqs", endpoint_url=self._settings.sqs_endpoint_url
            ) as sqs:
                await sqs.change_message_visibility(
                    QueueUrl=queue_url,
                    ReceiptHandle=receipt_handle,
                    VisibilityTimeout=timeout,
                )
        except Exception:
            logger.exception("Failed to change message visibility")

    def _parse_message(self, raw: dict) -> QueueMessage:
        body = json.loads(raw["Body"])

        if "ingestion_id" in body:
            return QueueMessage(**body)

        # Handle simplified format: {file_id, user_id, file_type, s3_url, processing_steps}
        s3_url: str = body.get("s3_url", "")
        bucket, key = self._parse_s3_url(s3_url)
        file_type = body.get("file_type", "text")

        pipeline_map = {
            "transcribe": ProcessingPipeline.TRANSCRIPTION,
            "parse": ProcessingPipeline.OCR,
            "embed": ProcessingPipeline.EMBEDDING,
        }
        steps = body.get("processing_steps", [])
        pipelines = [pipeline_map[s] for s in steps if s in pipeline_map]
        if not pipelines:
            pipelines = [ProcessingPipeline.EMBEDDING]

        return QueueMessage(
            ingestion_id=body.get("file_id", ""),
            filename=key.rsplit("/", 1)[-1] if key else "",
            s3_bucket=bucket,
            s3_key=key,
            file_category=FileCategory(file_type),
            mime_type="application/octet-stream",
            size_bytes=0,
            checksum_sha256="",
            pipelines=pipelines,
            metadata={"user_id": body.get("user_id", "")},
        )

    @staticmethod
    def _parse_s3_url(url: str) -> tuple[str, str]:
        """Extract bucket and key from s3://bucket/key or https://bucket.s3...amazonaws.com/key."""
        if url.startswith("s3://"):
            parts = url[5:].split("/", 1)
            return parts[0], parts[1] if len(parts) > 1 else ""
        if ".s3." in url or ".s3-" in url:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            bucket = parsed.hostname.split(".")[0] if parsed.hostname else ""
            key = parsed.path.lstrip("/")
            return bucket, key
        return "", url
