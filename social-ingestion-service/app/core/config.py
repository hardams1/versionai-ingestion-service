from __future__ import annotations

from functools import lru_cache
from typing import List, Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    app_name: str = "VersionAI Social Ingestion Service"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    host: str = "0.0.0.0"
    port: int = 8012

    database_url: str = "sqlite+aiosqlite:///./social_ingestion.db"

    jwt_secret_key: str = "versionai-dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"

    token_encryption_key: str = Field(
        default="versionai-token-encryption-key-change-me",
        description="Fernet-compatible key for encrypting OAuth tokens at rest",
    )

    redis_url: str = "redis://localhost:6379/3"

    # Platform OAuth credentials
    twitter_client_id: Optional[str] = None
    twitter_client_secret: Optional[str] = None
    facebook_app_id: Optional[str] = None
    facebook_app_secret: Optional[str] = None
    instagram_app_id: Optional[str] = None
    instagram_app_secret: Optional[str] = None
    tiktok_client_key: Optional[str] = None
    tiktok_client_secret: Optional[str] = None
    snapchat_client_id: Optional[str] = None
    snapchat_client_secret: Optional[str] = None

    oauth_redirect_base_url: str = "http://localhost:3000/settings/social/callback"

    # Sibling services
    processing_service_url: str = "http://localhost:8001"
    brain_service_url: str = "http://localhost:8002"
    ingestion_service_url: str = "http://localhost:8000"

    # Scheduling
    sync_interval_hours: int = Field(default=6, ge=1, description="Auto-sync interval")
    max_items_per_sync: int = Field(default=200, ge=10)

    cors_origins: List[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
