from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import Settings, get_settings
from app.services.avatar_profile import (
    AvatarProfileService,
    BaseAvatarProfileStore,
    LocalAvatarProfileStore,
    S3AvatarProfileStore,
)
from app.services.image_validator import ImageValidator
from app.services.ingestion_client import IngestionClient
from app.services.renderer import BaseRenderer, create_renderer

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
def get_renderer() -> BaseRenderer:
    return create_renderer(get_settings())


@lru_cache
def get_image_validator() -> ImageValidator:
    return ImageValidator(get_settings())


@lru_cache
def get_avatar_profile_store() -> BaseAvatarProfileStore:
    settings = get_settings()
    if settings.avatar_profile_storage == "s3":
        return S3AvatarProfileStore(settings)
    return LocalAvatarProfileStore(settings)


@lru_cache
def get_avatar_profile_service() -> AvatarProfileService:
    return AvatarProfileService(
        get_avatar_profile_store(),
        get_image_validator(),
        get_settings(),
    )


@lru_cache
def get_ingestion_client() -> IngestionClient:
    return IngestionClient(get_settings())
