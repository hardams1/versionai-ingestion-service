from __future__ import annotations

import base64
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

import aioboto3

from app.config import Settings
from app.models.enums import ImageSourceType, RendererProvider
from app.models.schemas import AvatarProfile
from app.services.image_validator import ImageMetadata, ImageValidator
from app.utils.exceptions import (
    AvatarProfileNotFoundError,
    AvatarProfileStorageError,
    InvalidImageError,
    MissingImageInputError,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract profile store
# ---------------------------------------------------------------------------

class BaseAvatarProfileStore(ABC):

    @abstractmethod
    async def get_profile(self, user_id: str) -> AvatarProfile:
        """Retrieve the avatar profile for a user. Raises AvatarProfileNotFoundError if missing."""

    @abstractmethod
    async def save_profile(self, profile: AvatarProfile) -> None:
        """Persist an avatar profile."""

    @abstractmethod
    async def delete_profile(self, user_id: str) -> None:
        """Remove an avatar profile."""

    @abstractmethod
    async def list_profiles(self) -> list[AvatarProfile]:
        """Return all stored profiles."""

    @abstractmethod
    async def store_image(self, user_id: str, avatar_id: str, image_bytes: bytes, fmt: str) -> str:
        """Store validated face image and return its path/key."""

    @abstractmethod
    async def delete_image(self, image_path: str) -> None:
        """Delete a stored face image."""


# ---------------------------------------------------------------------------
# Local filesystem store
# ---------------------------------------------------------------------------

class LocalAvatarProfileStore(BaseAvatarProfileStore):

    def __init__(self, settings: Settings) -> None:
        self._profiles_dir = Path(settings.avatar_profiles_dir)
        self._images_dir = Path(settings.avatar_images_dir)
        self._profiles_dir.mkdir(parents=True, exist_ok=True)
        self._images_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, user_id: str) -> Path:
        return self._profiles_dir / f"{user_id}.json"

    async def get_profile(self, user_id: str) -> AvatarProfile:
        path = self._path(user_id)
        if not path.exists():
            raise AvatarProfileNotFoundError(user_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return AvatarProfile(**data)
        except AvatarProfileNotFoundError:
            raise
        except Exception as exc:
            raise AvatarProfileStorageError(f"Failed to read profile for '{user_id}': {exc}") from exc

    async def save_profile(self, profile: AvatarProfile) -> None:
        path = self._path(profile.user_id)
        try:
            path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
            logger.info("Saved avatar profile for user=%s avatar_id=%s", profile.user_id, profile.avatar_id)
        except Exception as exc:
            raise AvatarProfileStorageError(f"Failed to save profile: {exc}") from exc

    async def delete_profile(self, user_id: str) -> None:
        path = self._path(user_id)
        if not path.exists():
            raise AvatarProfileNotFoundError(user_id)
        profile = await self.get_profile(user_id)
        path.unlink()
        await self.delete_image(profile.source_image_path)
        logger.info("Deleted avatar profile for user=%s", user_id)

    async def list_profiles(self) -> list[AvatarProfile]:
        profiles: list[AvatarProfile] = []
        for f in self._profiles_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                profiles.append(AvatarProfile(**data))
            except Exception:
                logger.warning("Skipping corrupt profile file: %s", f.name)
        return profiles

    async def store_image(self, user_id: str, avatar_id: str, image_bytes: bytes, fmt: str) -> str:
        ext = "jpg" if fmt == "JPEG" else fmt.lower()
        filename = f"{user_id}_{avatar_id}.{ext}"
        dest = self._images_dir / filename
        try:
            dest.write_bytes(image_bytes)
            logger.info("Stored face image: %s (%d bytes)", dest, len(image_bytes))
            return str(dest)
        except Exception as exc:
            raise AvatarProfileStorageError(f"Failed to store image: {exc}") from exc

    async def delete_image(self, image_path: str) -> None:
        try:
            p = Path(image_path)
            if p.exists():
                p.unlink()
                logger.info("Deleted face image: %s", image_path)
        except Exception:
            logger.warning("Failed to delete image: %s", image_path)


# ---------------------------------------------------------------------------
# S3 store
# ---------------------------------------------------------------------------

class S3AvatarProfileStore(BaseAvatarProfileStore):

    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.s3_bucket_name
        self._profiles_prefix = settings.s3_avatar_profiles_prefix
        self._images_prefix = settings.s3_avatar_images_prefix
        self._region = settings.aws_region
        self._endpoint_url = settings.s3_endpoint_url
        self._session = aioboto3.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=self._region,
        )

    def _profile_key(self, user_id: str) -> str:
        return f"{self._profiles_prefix}/{user_id}.json"

    def _image_key(self, user_id: str, avatar_id: str, fmt: str) -> str:
        ext = "jpg" if fmt == "JPEG" else fmt.lower()
        return f"{self._images_prefix}/{user_id}_{avatar_id}.{ext}"

    async def get_profile(self, user_id: str) -> AvatarProfile:
        try:
            async with self._session.client("s3", endpoint_url=self._endpoint_url) as s3:
                resp = await s3.get_object(Bucket=self._bucket, Key=self._profile_key(user_id))
                body = await resp["Body"].read()
                return AvatarProfile(**json.loads(body))
        except Exception as exc:
            if "NoSuchKey" in str(exc) or "404" in str(exc):
                raise AvatarProfileNotFoundError(user_id) from exc
            raise AvatarProfileStorageError(f"S3 profile fetch failed: {exc}") from exc

    async def save_profile(self, profile: AvatarProfile) -> None:
        try:
            async with self._session.client("s3", endpoint_url=self._endpoint_url) as s3:
                await s3.put_object(
                    Bucket=self._bucket,
                    Key=self._profile_key(profile.user_id),
                    Body=profile.model_dump_json(indent=2).encode(),
                    ContentType="application/json",
                )
            logger.info("Saved avatar profile to S3 for user=%s", profile.user_id)
        except Exception as exc:
            raise AvatarProfileStorageError(f"S3 profile save failed: {exc}") from exc

    async def delete_profile(self, user_id: str) -> None:
        profile = await self.get_profile(user_id)
        try:
            async with self._session.client("s3", endpoint_url=self._endpoint_url) as s3:
                await s3.delete_object(Bucket=self._bucket, Key=self._profile_key(user_id))
            await self.delete_image(profile.source_image_path)
            logger.info("Deleted avatar profile from S3 for user=%s", user_id)
        except AvatarProfileNotFoundError:
            raise
        except Exception as exc:
            raise AvatarProfileStorageError(f"S3 profile delete failed: {exc}") from exc

    async def list_profiles(self) -> list[AvatarProfile]:
        profiles: list[AvatarProfile] = []
        try:
            async with self._session.client("s3", endpoint_url=self._endpoint_url) as s3:
                paginator = s3.get_paginator("list_objects_v2")
                async for page in paginator.paginate(Bucket=self._bucket, Prefix=self._profiles_prefix):
                    for obj in page.get("Contents", []):
                        if obj["Key"].endswith(".json"):
                            resp = await s3.get_object(Bucket=self._bucket, Key=obj["Key"])
                            body = await resp["Body"].read()
                            profiles.append(AvatarProfile(**json.loads(body)))
        except Exception as exc:
            raise AvatarProfileStorageError(f"S3 list profiles failed: {exc}") from exc
        return profiles

    async def store_image(self, user_id: str, avatar_id: str, image_bytes: bytes, fmt: str) -> str:
        key = self._image_key(user_id, avatar_id, fmt)
        ct = "image/jpeg" if fmt == "JPEG" else "image/png"
        try:
            async with self._session.client("s3", endpoint_url=self._endpoint_url) as s3:
                await s3.put_object(
                    Bucket=self._bucket, Key=key, Body=image_bytes, ContentType=ct,
                )
            logger.info("Stored face image to S3: s3://%s/%s (%d bytes)", self._bucket, key, len(image_bytes))
            return f"s3://{self._bucket}/{key}"
        except Exception as exc:
            raise AvatarProfileStorageError(f"S3 image store failed: {exc}") from exc

    async def delete_image(self, image_path: str) -> None:
        try:
            if image_path.startswith("s3://"):
                parts = image_path.replace("s3://", "").split("/", 1)
                if len(parts) == 2:
                    async with self._session.client("s3", endpoint_url=self._endpoint_url) as s3:
                        await s3.delete_object(Bucket=parts[0], Key=parts[1])
                    logger.info("Deleted S3 image: %s", image_path)
        except Exception:
            logger.warning("Failed to delete S3 image: %s", image_path)

    async def ensure_bucket_exists(self) -> None:
        try:
            async with self._session.client("s3", endpoint_url=self._endpoint_url) as s3:
                try:
                    await s3.head_bucket(Bucket=self._bucket)
                except Exception:
                    await s3.create_bucket(Bucket=self._bucket)
                    logger.info("Created S3 bucket: %s", self._bucket)
        except Exception as exc:
            logger.warning("Could not ensure bucket exists: %s", exc)


# ---------------------------------------------------------------------------
# Service layer
# ---------------------------------------------------------------------------

class AvatarProfileService:
    """High-level avatar profile management.

    Per system requirements:
    - Map user_id → avatar profile with VALIDATED photorealistic face image
    - Ensure visual identity consistency
    - NEVER generate random or generic faces
    - Source images must pass photorealistic quality gates
    """

    def __init__(
        self,
        store: BaseAvatarProfileStore,
        validator: ImageValidator,
        settings: Settings,
    ) -> None:
        self._store = store
        self._validator = validator
        self._settings = settings

    async def resolve_avatar(self, user_id: str) -> AvatarProfile:
        """Return the avatar profile for a user.

        In development mode with mock renderer, auto-creates a placeholder profile.
        In production, raises AvatarProfileNotFoundError so callers register a real profile.
        """
        try:
            return await self._store.get_profile(user_id)
        except AvatarProfileNotFoundError:
            if self._settings.environment == "development" and self._settings.renderer_provider == "mock":
                logger.info("Auto-creating default avatar profile for user=%s (development mock mode)", user_id)
                return await self._get_or_create_default(user_id)
            raise

    async def _get_or_create_default(self, user_id: str) -> AvatarProfile:
        """Create a minimal avatar profile for development/mock mode."""
        now = datetime.now(timezone.utc)
        profile = AvatarProfile(
            user_id=user_id,
            avatar_id=f"default-{user_id}",
            source_image_path="mock://default-avatar.png",
            provider=RendererProvider.MOCK,
            display_name=f"Default Avatar ({user_id})",
            expression_baseline="neutral",
            image_width=512,
            image_height=512,
            image_format="PNG",
            image_source=ImageSourceType.UPLOAD,
            created_at=now,
            updated_at=now,
        )
        await self._store.save_profile(profile)
        return profile

    async def create_profile(
        self,
        user_id: str,
        avatar_id: str,
        image_bytes: bytes,
        provider: RendererProvider,
        display_name: str | None = None,
        expression_baseline: str = "neutral",
        image_source: ImageSourceType = ImageSourceType.UPLOAD,
    ) -> AvatarProfile:
        """Create an avatar profile with a validated photorealistic face image.

        Steps:
        1. Validate image bytes (format, resolution, color, realism gates)
        2. Store validated image
        3. Save profile referencing stored image
        """
        meta = self._validator.validate(image_bytes)

        stored_path = await self._store.store_image(user_id, avatar_id, image_bytes, meta.format)

        now = datetime.now(timezone.utc)
        profile = AvatarProfile(
            user_id=user_id,
            avatar_id=avatar_id,
            source_image_path=stored_path,
            provider=provider,
            display_name=display_name,
            expression_baseline=expression_baseline,
            image_width=meta.width,
            image_height=meta.height,
            image_format=meta.format,
            image_source=image_source,
            created_at=now,
            updated_at=now,
        )
        await self._store.save_profile(profile)
        return profile

    async def create_from_base64(
        self,
        user_id: str,
        avatar_id: str,
        image_base64: str,
        provider: RendererProvider,
        display_name: str | None = None,
        expression_baseline: str = "neutral",
    ) -> AvatarProfile:
        """Decode base64 image and create a validated avatar profile."""
        try:
            image_bytes = base64.b64decode(image_base64, validate=True)
        except Exception as exc:
            raise InvalidImageError(f"Failed to decode base64 image: {exc}") from exc

        if not image_bytes:
            raise MissingImageInputError()

        return await self.create_profile(
            user_id=user_id,
            avatar_id=avatar_id,
            image_bytes=image_bytes,
            provider=provider,
            display_name=display_name,
            expression_baseline=expression_baseline,
            image_source=ImageSourceType.UPLOAD,
        )

    async def delete_profile(self, user_id: str) -> None:
        await self._store.delete_profile(user_id)

    async def list_profiles(self) -> list[AvatarProfile]:
        return await self._store.list_profiles()
