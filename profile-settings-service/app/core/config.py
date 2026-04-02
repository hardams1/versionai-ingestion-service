from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    app_name: str = "VersionAI Profile & Settings Service"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    host: str = "0.0.0.0"
    port: int = 8007

    database_url: str = "sqlite+aiosqlite:///./profile_settings.db"

    jwt_secret_key: str = "change-me-to-a-long-random-string"
    jwt_algorithm: str = "HS256"

    # Image storage
    image_storage_mode: Literal["local", "s3"] = "local"
    local_upload_dir: str = "./uploads"
    image_serve_base_url: str = "http://localhost:8007/static/uploads"

    # S3 settings (for production)
    aws_region: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    s3_bucket_name: str = "versionai-profiles"
    s3_endpoint_url: str | None = None
    s3_prefix: str = "user"

    # Sibling services
    auth_service_url: str = "http://localhost:8006"
    brain_service_url: str = "http://localhost:8002"
    video_avatar_service_url: str = "http://localhost:8004"
    voice_service_url: str = "http://localhost:8003"
    orchestrator_service_url: str = "http://localhost:8005"

    # Image constraints
    max_image_size_bytes: int = Field(default=20 * 1024 * 1024, description="20 MB max")
    allowed_image_types: list[str] = Field(default=["image/jpeg", "image/png", "image/webp"])
    image_max_dimension: int = 4096
    image_target_size: int = Field(default=1024, description="Resize to this max dimension")
    image_quality: int = Field(default=85, description="JPEG quality for compression")

    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
