from __future__ import annotations

import io
import logging
import uuid
from pathlib import Path

from PIL import Image

from app.core.config import Settings

logger = logging.getLogger(__name__)


class ImageService:
    """Handles image validation, compression, and storage."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._upload_dir = Path(settings.local_upload_dir)
        self._upload_dir.mkdir(parents=True, exist_ok=True)

    def validate_content_type(self, content_type: str) -> bool:
        return content_type in self._settings.allowed_image_types

    async def process_and_store(
        self, file_bytes: bytes, user_id: str, content_type: str
    ) -> tuple[str, str]:
        """Validate, compress, and store image. Returns (public_url, storage_key)."""
        img = Image.open(io.BytesIO(file_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        max_dim = self._settings.image_target_size
        if img.width > max_dim or img.height > max_dim:
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=self._settings.image_quality, optimize=True)
        compressed = buf.getvalue()

        filename = f"{user_id}_profile.jpg"
        storage_key = f"user/{user_id}/{filename}"

        if self._settings.image_storage_mode == "local":
            url, key = await self._store_local(compressed, user_id, filename, storage_key)
        else:
            url, key = await self._store_s3(compressed, storage_key)

        logger.info(
            "Stored profile image for user=%s: %d→%d bytes, %dx%d",
            user_id, len(file_bytes), len(compressed), img.width, img.height,
        )
        return url, key

    async def _store_local(
        self, data: bytes, user_id: str, filename: str, storage_key: str
    ) -> tuple[str, str]:
        user_dir = self._upload_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        dest = user_dir / filename
        dest.write_bytes(data)
        url = f"{self._settings.image_serve_base_url}/{user_id}/{filename}"
        return url, storage_key

    async def _store_s3(self, data: bytes, storage_key: str) -> tuple[str, str]:
        try:
            import aioboto3
            session = aioboto3.Session()
            async with session.client(
                "s3",
                region_name=self._settings.aws_region,
                aws_access_key_id=self._settings.aws_access_key_id,
                aws_secret_access_key=self._settings.aws_secret_access_key,
                endpoint_url=self._settings.s3_endpoint_url,
            ) as s3:
                await s3.put_object(
                    Bucket=self._settings.s3_bucket_name,
                    Key=storage_key,
                    Body=data,
                    ContentType="image/jpeg",
                )
            url = f"https://{self._settings.s3_bucket_name}.s3.{self._settings.aws_region}.amazonaws.com/{storage_key}"
            return url, storage_key
        except Exception as exc:
            logger.error("S3 upload failed, falling back to local: %s", exc)
            return await self._store_local(data, storage_key.split("/")[1], "profile.jpg", storage_key)

    def get_image_as_base64(self, user_id: str) -> str | None:
        """Read the stored profile image and return as base64 for avatar sync."""
        import base64
        path = self._upload_dir / user_id / f"{user_id}_profile.jpg"
        if not path.exists():
            return None
        return base64.b64encode(path.read_bytes()).decode()
