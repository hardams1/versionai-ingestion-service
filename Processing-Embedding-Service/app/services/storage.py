from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import aioboto3

from app.utils.exceptions import FileDownloadError

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


class S3Fetcher:
    """Downloads files from S3 to local temp storage for processing."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._session = aioboto3.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )

    async def download(self, bucket: str, key: str) -> Path:
        """
        Download an S3 object to a temp file.
        Returns the local file path. Caller is responsible for cleanup.
        """
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
