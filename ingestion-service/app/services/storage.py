from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import aioboto3

from app.config import Settings
from app.models.enums import FileCategory
from app.utils.exceptions import StorageError

logger = logging.getLogger(__name__)


class S3StorageService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._session = aioboto3.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )

    def _build_s3_key(self, filename: str, category: FileCategory) -> str:
        date_prefix = datetime.now(timezone.utc).strftime("%Y/%m/%d")
        unique_id = uuid.uuid4().hex[:12]
        safe_name = filename.replace(" ", "_")
        return f"{self._settings.s3_prefix}/{category.value}/{date_prefix}/{unique_id}_{safe_name}"

    async def upload(
        self,
        file_bytes: bytes,
        filename: str,
        category: FileCategory,
        mime_type: str,
        checksum: str,
    ) -> str:
        """Upload file bytes to S3 and return the object key."""
        s3_key = self._build_s3_key(filename, category)
        bucket = self._settings.s3_bucket_name
        logger.info("Uploading '%s' to s3://%s/%s", filename, bucket, s3_key)

        extra_args: dict = {
            "ContentType": mime_type,
            "Metadata": {
                "original-filename": filename,
                "category": category.value,
                "sha256": checksum,
            },
        }

        try:
            async with self._session.client(
                "s3", endpoint_url=self._settings.s3_endpoint_url
            ) as s3:
                await s3.put_object(
                    Bucket=bucket,
                    Key=s3_key,
                    Body=file_bytes,
                    **extra_args,
                )
        except Exception as exc:
            logger.exception("S3 upload failed for '%s'", filename)
            raise StorageError(f"Failed to upload '{filename}' to S3: {exc}") from exc

        logger.info("Upload complete: s3://%s/%s", bucket, s3_key)
        return s3_key

    async def ensure_bucket_exists(self) -> None:
        """Create the bucket if it doesn't exist (useful for local dev with MinIO/LocalStack)."""
        bucket = self._settings.s3_bucket_name
        try:
            async with self._session.client(
                "s3", endpoint_url=self._settings.s3_endpoint_url
            ) as s3:
                try:
                    await s3.head_bucket(Bucket=bucket)
                    logger.info("Bucket '%s' already exists", bucket)
                except Exception:
                    await s3.create_bucket(Bucket=bucket)
                    logger.info("Created bucket '%s'", bucket)
        except Exception as exc:
            logger.warning("Could not verify/create bucket '%s': %s", bucket, exc)
