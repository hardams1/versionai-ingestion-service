from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings
from app.models.enums import FileCategory
from app.utils.exceptions import StorageError

logger = logging.getLogger(__name__)


class BaseStorageService(ABC):
    @abstractmethod
    async def upload(
        self, file_bytes: bytes, filename: str, category: FileCategory,
        mime_type: str, checksum: str,
    ) -> str: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    async def ensure_bucket_exists(self) -> None: ...

    @staticmethod
    def _build_key(prefix: str, filename: str, category: FileCategory) -> str:
        date_prefix = datetime.now(timezone.utc).strftime("%Y/%m/%d")
        unique_id = uuid.uuid4().hex[:12]
        safe_name = filename.replace(" ", "_")
        return f"{prefix}/{category.value}/{date_prefix}/{unique_id}_{safe_name}"


class LocalStorageService(BaseStorageService):
    """Stores files on the local filesystem — used when S3 is not configured."""

    def __init__(self, settings: Settings) -> None:
        self._root = Path(settings.local_storage_path)
        self._prefix = settings.s3_prefix

    async def upload(
        self, file_bytes: bytes, filename: str, category: FileCategory,
        mime_type: str, checksum: str,
    ) -> str:
        key = self._build_key(self._prefix, filename, category)
        dest = self._root / key
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(file_bytes)
        except Exception as exc:
            logger.exception("Local storage write failed for '%s'", filename)
            raise StorageError(f"Failed to store '{filename}' locally: {exc}") from exc

        logger.info("Stored locally: %s (%d bytes)", dest, len(file_bytes))
        return key

    async def delete(self, key: str) -> None:
        dest = self._root / key
        try:
            dest.unlink(missing_ok=True)
            logger.info("Deleted local file: %s", dest)
        except Exception:
            logger.exception("Failed to delete local file: %s", dest)

    async def ensure_bucket_exists(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        logger.info("Local storage directory ready: %s", self._root.resolve())


class S3StorageService(BaseStorageService):
    """Stores files in AWS S3 (or S3-compatible services like MinIO / LocalStack)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        import aioboto3
        self._session = aioboto3.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )

    async def upload(
        self, file_bytes: bytes, filename: str, category: FileCategory,
        mime_type: str, checksum: str,
    ) -> str:
        s3_key = self._build_key(self._settings.s3_prefix, filename, category)
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
                    Bucket=bucket, Key=s3_key, Body=file_bytes, **extra_args,
                )
        except Exception as exc:
            logger.exception("S3 upload failed for '%s'", filename)
            raise StorageError(f"Failed to upload '{filename}' to S3: {exc}") from exc

        logger.info("Upload complete: s3://%s/%s", bucket, s3_key)
        return s3_key

    async def delete(self, key: str) -> None:
        bucket = self._settings.s3_bucket_name
        try:
            async with self._session.client(
                "s3", endpoint_url=self._settings.s3_endpoint_url
            ) as s3:
                await s3.delete_object(Bucket=bucket, Key=key)
            logger.info("Deleted s3://%s/%s", bucket, key)
        except Exception:
            logger.exception("Failed to delete s3://%s/%s", bucket, key)

    async def ensure_bucket_exists(self) -> None:
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
