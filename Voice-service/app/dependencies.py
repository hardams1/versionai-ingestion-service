from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import Settings, get_settings
from app.services.tts import BaseTTSEngine, create_tts_engine
from app.services.voice_profile import (
    BaseVoiceProfileStore,
    LocalVoiceProfileStore,
    S3VoiceProfileStore,
    VoiceProfileService,
)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    settings: Settings = Depends(get_settings),
    api_key: str | None = Security(api_key_header),
) -> None:
    """If an API key is configured, enforce it on every request."""
    if settings.api_key is None:
        return
    if api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")


@lru_cache
def get_tts_engine() -> BaseTTSEngine:
    return create_tts_engine(get_settings())


@lru_cache
def get_voice_profile_store() -> BaseVoiceProfileStore:
    settings = get_settings()
    if settings.voice_profile_storage == "s3":
        return S3VoiceProfileStore(settings)
    return LocalVoiceProfileStore(settings)


@lru_cache
def get_voice_profile_service() -> VoiceProfileService:
    return VoiceProfileService(get_voice_profile_store(), get_settings())
