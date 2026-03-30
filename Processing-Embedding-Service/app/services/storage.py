from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import aioboto3

from app.utils.exceptions import FileDownloadError

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


class S3Fetcher:
    """Downloads files from S3 (or local storage fallback) for processing."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._local_path = Path(settings.local_storage_path) if settings.local_storage_path else None
        self._session = aioboto3.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )

    async def download(self, bucket: str, key: str) -> Path:
        """
        Download a file to a temp path. Tries local storage first (if configured),
        then falls back to S3.
        """
        if self._local_path:
            return await self._download_local(key)
        return await self._download_s3(bucket, key)

    async def _download_local(self, key: str) -> Path:
        assert self._local_path is not None
        source = self._local_path / key
        if not source.exists():
            raise FileDownloadError(f"Local file not found: {source}")

        suffix = source.suffix or ""
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="pes_")
        tmp_path = Path(tmp.name)
        tmp.close()

        try:
            shutil.copy2(source, tmp_path)
            size = tmp_path.stat().st_size
            logger.info("Copied local file %s -> %s (%d bytes)", source, tmp_path, size)
            return tmp_path
        except Exception as exc:
            tmp_path.unlink(missing_ok=True)
            raise FileDownloadError(f"Failed to copy local file {source}: {exc}") from exc

    async def _download_s3(self, bucket: str, key: str) -> Path:
        suffix = Path(key).suffix or ""
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="pes_")
        tmp_path = Path(tmp.name)
        tmp.close()

        logger.info("Downloading s3://%s/%s -> %s", bucket, key, tmp_path)

        try:
            async with self._session.client(
                "s3", endpoint_url=self._settings.s3_endpoint_url
            ) as s3:
                await s3.download_file(bucket, key, str(tmp_path))

            size = tmp_path.stat().st_size
            logger.info("Downloaded %d bytes to %s", size, tmp_path)
            return tmp_path

        except Exception as exc:
            tmp_path.unlink(missing_ok=True)
            raise FileDownloadError(
                f"Failed to download s3://{bucket}/{key}: {exc}"
            ) from exc
