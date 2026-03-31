from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

import aioboto3

from app.config import Settings
from app.models.enums import TTSProvider
from app.models.schemas import VoiceProfile
from app.utils.exceptions import VoiceProfileNotFoundError, VoiceProfileStorageError

logger = logging.getLogger(__name__)


class BaseVoiceProfileStore(ABC):
    """Abstract voice profile storage."""

    @abstractmethod
    async def get_profile(self, user_id: str) -> VoiceProfile:
        """Retrieve the voice profile for a user. Raises VoiceProfileNotFoundError if missing."""

    @abstractmethod
    async def save_profile(self, profile: VoiceProfile) -> None:
        """Persist a voice profile."""

    @abstractmethod
    async def delete_profile(self, user_id: str) -> None:
        """Remove a voice profile."""

    @abstractmethod
    async def list_profiles(self) -> list[VoiceProfile]:
        """Return all stored profiles."""


class LocalVoiceProfileStore(BaseVoiceProfileStore):
    """File-system backed profile store — one JSON file per user."""

    def __init__(self, settings: Settings) -> None:
        self._base_dir = Path(settings.voice_profiles_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, user_id: str) -> Path:
        return self._base_dir / f"{user_id}.json"

    async def get_profile(self, user_id: str) -> VoiceProfile:
        path = self._path(user_id)
        if not path.exists():
            raise VoiceProfileNotFoundError(user_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return VoiceProfile(**data)
        except Exception as exc:
            raise VoiceProfileStorageError(f"Failed to read profile for '{user_id}': {exc}") from exc

    async def save_profile(self, profile: VoiceProfile) -> None:
        path = self._path(profile.user_id)
        try:
            path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
            logger.info("Saved voice profile for user=%s voice_id=%s", profile.user_id, profile.voice_id)
        except Exception as exc:
            raise VoiceProfileStorageError(f"Failed to save profile: {exc}") from exc

    async def delete_profile(self, user_id: str) -> None:
        path = self._path(user_id)
        if not path.exists():
            raise VoiceProfileNotFoundError(user_id)
        path.unlink()
        logger.info("Deleted voice profile for user=%s", user_id)

    async def list_profiles(self) -> list[VoiceProfile]:
        profiles: list[VoiceProfile] = []
        for f in self._base_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                profiles.append(VoiceProfile(**data))
            except Exception:
                logger.warning("Skipping corrupt profile file: %s", f.name)
        return profiles


class S3VoiceProfileStore(BaseVoiceProfileStore):
    """S3-backed profile store — objects at {prefix}/{user_id}.json."""

    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.s3_bucket_name
        self._prefix = settings.s3_voice_profiles_prefix
        self._region = settings.aws_region
        self._endpoint_url = settings.s3_endpoint_url
        self._session = aioboto3.Session(
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=self._region,
        )

    def _key(self, user_id: str) -> str:
        return f"{self._prefix}/{user_id}.json"

    async def get_profile(self, user_id: str) -> VoiceProfile:
        try:
            async with self._session.client("s3", endpoint_url=self._endpoint_url) as s3:
                resp = await s3.get_object(Bucket=self._bucket, Key=self._key(user_id))
                body = await resp["Body"].read()
                return VoiceProfile(**json.loads(body))
        except Exception as exc:
            if "NoSuchKey" in str(exc) or "404" in str(exc):
                raise VoiceProfileNotFoundError(user_id) from exc
            raise VoiceProfileStorageError(f"S3 profile fetch failed: {exc}") from exc

    async def save_profile(self, profile: VoiceProfile) -> None:
        try:
            async with self._session.client("s3", endpoint_url=self._endpoint_url) as s3:
                await s3.put_object(
                    Bucket=self._bucket,
                    Key=self._key(profile.user_id),
                    Body=profile.model_dump_json(indent=2).encode(),
                    ContentType="application/json",
                )
            logger.info("Saved voice profile to S3 for user=%s", profile.user_id)
        except Exception as exc:
            raise VoiceProfileStorageError(f"S3 profile save failed: {exc}") from exc

    async def delete_profile(self, user_id: str) -> None:
        try:
            async with self._session.client("s3", endpoint_url=self._endpoint_url) as s3:
                await s3.delete_object(Bucket=self._bucket, Key=self._key(user_id))
            logger.info("Deleted voice profile from S3 for user=%s", user_id)
        except Exception as exc:
            raise VoiceProfileStorageError(f"S3 profile delete failed: {exc}") from exc

    async def list_profiles(self) -> list[VoiceProfile]:
        profiles: list[VoiceProfile] = []
        try:
            async with self._session.client("s3", endpoint_url=self._endpoint_url) as s3:
                paginator = s3.get_paginator("list_objects_v2")
                async for page in paginator.paginate(Bucket=self._bucket, Prefix=self._prefix):
                    for obj in page.get("Contents", []):
                        if obj["Key"].endswith(".json"):
                            resp = await s3.get_object(Bucket=self._bucket, Key=obj["Key"])
                            body = await resp["Body"].read()
                            profiles.append(VoiceProfile(**json.loads(body)))
        except Exception as exc:
            raise VoiceProfileStorageError(f"S3 list profiles failed: {exc}") from exc
        return profiles

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


class VoiceProfileService:
    """High-level voice profile resolution.

    Wraps the storage backend and adds fallback logic:
    if a user has no profile, a sensible default is returned based on
    the configured TTS provider.
    """

    def __init__(self, store: BaseVoiceProfileStore, settings: Settings) -> None:
        self._store = store
        self._settings = settings

    async def resolve_voice(self, user_id: str) -> VoiceProfile:
        """Return the voice profile for a user.

        In development mode, auto-creates a default profile when none exists.
        In production, raises VoiceProfileNotFoundError so callers register a profile first.
        """
        try:
            return await self._store.get_profile(user_id)
        except VoiceProfileNotFoundError:
            if self._settings.environment == "development":
                logger.info("Auto-creating default voice profile for user=%s (development mode)", user_id)
                return await self.get_or_create_default(user_id)
            raise

    async def get_or_create_default(self, user_id: str) -> VoiceProfile:
        """Return existing profile or create a default one.

        Use only during initial onboarding — production callers should
        use resolve_voice() to enforce the 'no generic voices' rule.
        """
        try:
            return await self._store.get_profile(user_id)
        except VoiceProfileNotFoundError:
            default = self._build_default_profile(user_id)
            await self._store.save_profile(default)
            logger.info("Created default voice profile for user=%s", user_id)
            return default

    async def create_profile(self, user_id: str, voice_id: str, provider: TTSProvider, display_name: str | None = None) -> VoiceProfile:
        now = datetime.now(timezone.utc)
        profile = VoiceProfile(
            user_id=user_id,
            voice_id=voice_id,
            provider=provider,
            display_name=display_name,
            created_at=now,
            updated_at=now,
        )
        await self._store.save_profile(profile)
        return profile

    async def delete_profile(self, user_id: str) -> None:
        await self._store.delete_profile(user_id)

    async def list_profiles(self) -> list[VoiceProfile]:
        return await self._store.list_profiles()

    def _build_default_profile(self, user_id: str) -> VoiceProfile:
        provider = self._settings.tts_provider
        if provider == "openai":
            voice_id = self._settings.openai_tts_default_voice
        elif provider == "elevenlabs":
            voice_id = self._settings.elevenlabs_default_voice_id or "default"
        else:
            voice_id = "mock-voice"
        return VoiceProfile(
            user_id=user_id,
            voice_id=voice_id,
            provider=TTSProvider(self._settings.tts_provider),
        )
