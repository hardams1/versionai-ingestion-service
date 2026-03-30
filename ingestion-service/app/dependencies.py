from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import Settings, get_settings
from app.services.metadata import MetadataService
from app.services.queue import SQSPublisher
from app.services.storage import BaseStorageService, LocalStorageService, S3StorageService
from app.services.validation import FileValidator

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
def get_file_validator() -> FileValidator:
    return FileValidator(get_settings())


@lru_cache
def get_storage_service() -> BaseStorageService:
    settings = get_settings()
    if settings.use_local_storage:
        return LocalStorageService(settings)
    return S3StorageService(settings)


@lru_cache
def get_queue_publisher() -> SQSPublisher:
    return SQSPublisher(get_settings())


@lru_cache
def get_metadata_service() -> MetadataService:
    return MetadataService()
