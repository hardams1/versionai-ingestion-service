from __future__ import annotations

import logging
from dataclasses import dataclass

import aioboto3

from app.config import Settings
from app.utils.exceptions import IngestionDataNotFoundError

logger = logging.getLogger(__name__)

IMAGE_CONTENT_TYPES = frozenset({
    "image/jpeg",
    "image/png",
    "image/jpg",
})


@dataclass(frozen=True)
class IngestedImage:
    s3_key: str
    content_type: str
    size_bytes: int
    image_bytes: bytes


class IngestionClient:
    """Fetches user face images from the ingestion pipeline's S3 bucket.

    The ingestion service (microservice #1) stores uploaded files at:
        s3://{bucket}/{prefix}/{category}/{date}/{unique_id}_{filename}

    This client scans for image uploads belonging to a user_id and retrieves
    the best candidate for avatar creation.
    """

    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.ingestion_s3_bucket
        self._prefix = settings.ingestion_s3_prefix
        self._region = settings.aws_region
        self._endpoint_url = settings.s3_endpoint_url
        self._session = aioboto3.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=self._region,
        )

    async def fetch_user_face_image(self, user_id: str) -> IngestedImage:
        """Find and download the best face image for a user from ingestion S3.

        Scans the ingestion bucket for image objects whose key contains the
        user_id, then returns the largest qualifying image (best quality).
        """
        candidates = await self._list_user_images(user_id)
        if not candidates:
            raise IngestionDataNotFoundError(user_id)

        best = max(candidates, key=lambda c: c["Size"])
        logger.info(
            "Selected ingested image for user=%s: %s (%d bytes)",
            user_id, best["Key"], best["Size"],
        )

        image_bytes = await self._download_object(best["Key"])
        content_type = best.get("ContentType", "image/jpeg")

        return IngestedImage(
            s3_key=best["Key"],
            content_type=content_type,
            size_bytes=len(image_bytes),
            image_bytes=image_bytes,
        )

    async def _list_user_images(self, user_id: str) -> list[dict]:
        """List S3 objects that are images potentially belonging to user_id."""
        candidates: list[dict] = []
        try:
            async with self._session.client("s3", endpoint_url=self._endpoint_url) as s3:
                paginator = s3.get_paginator("list_objects_v2")
                async for page in paginator.paginate(
                    Bucket=self._bucket, Prefix=self._prefix
                ):
                    for obj in page.get("Contents", []):
                        key = obj["Key"]
                        if user_id not in key:
                            continue
                        lower = key.lower()
                        if any(lower.endswith(ext) for ext in (".jpg", ".jpeg", ".png")):
                            head = await s3.head_object(Bucket=self._bucket, Key=key)
                            ct = head.get("ContentType", "")
                            if ct in IMAGE_CONTENT_TYPES or any(
                                lower.endswith(ext) for ext in (".jpg", ".jpeg", ".png")
                            ):
                                candidates.append({
                                    "Key": key,
                                    "Size": obj["Size"],
                                    "ContentType": ct,
                                })
        except IngestionDataNotFoundError:
            raise
        except Exception as exc:
            logger.warning("Failed to list ingested images for user=%s: %s", user_id, exc)

        return candidates

    async def _download_object(self, key: str) -> bytes:
        async with self._session.client("s3", endpoint_url=self._endpoint_url) as s3:
            resp = await s3.get_object(Bucket=self._bucket, Key=key)
            return await resp["Body"].read()
