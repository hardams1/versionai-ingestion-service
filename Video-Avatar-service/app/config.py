from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # --- Application ---
    app_name: str = "VersionAI Video Avatar Service"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8004

    # --- Renderer provider ---
    # "auto" tries D-ID → SyncLabs → FFmpeg based on which API keys are set
    renderer_provider: Literal["synclabs", "d_id", "mock", "auto"] = "auto"

    # Sync Labs (lip-sync video generation)
    synclabs_api_key: str | None = None
    synclabs_api_url: str = "https://api.synclabs.so/v2"
    synclabs_model: str = "sync-1.7.1-beta"

    # D-ID (talking-head video generation)
    d_id_api_key: str | None = None
    d_id_api_url: str = "https://api.d-id.com"

    # --- Video output ---
    default_video_format: Literal["mp4", "webm"] = "mp4"
    default_resolution: str = Field(default="512x512", description="WxH pixels")
    default_fps: int = Field(default=25, ge=1, le=60)
    max_audio_duration_seconds: float = Field(default=300.0, description="Max input audio length")
    max_audio_size_bytes: int = Field(default=25 * 1024 * 1024, description="25 MB max upload")

    # --- Avatar profiles ---
    avatar_profile_storage: Literal["s3", "local"] = "local"
    avatar_profiles_dir: str = "./avatar_profiles"
    avatar_images_dir: str = "./avatar_images"

    # S3 avatar storage
    aws_region: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    s3_bucket_name: str = "versionai-avatars"
    s3_endpoint_url: str | None = None
    s3_avatar_profiles_prefix: str = "profiles"
    s3_avatar_images_prefix: str = "images"

    # --- Image validation (photorealistic quality gates) ---
    min_image_width: int = Field(default=256, description="Minimum face image width in pixels")
    min_image_height: int = Field(default=256, description="Minimum face image height in pixels")
    max_image_width: int = Field(default=4096, description="Maximum image width")
    max_image_height: int = Field(default=4096, description="Maximum image height")
    min_image_file_size: int = Field(default=5_000, description="Minimum bytes for a real photo")
    max_image_file_size: int = Field(default=20 * 1024 * 1024, description="20 MB max")
    allowed_image_formats: list[str] = Field(
        default=["JPEG", "PNG"],
        description="Only photorealistic-capable formats",
    )
    max_aspect_ratio: float = Field(default=2.0, description="Max w/h or h/w ratio")

    # --- Sibling services ---
    voice_service_url: str | None = Field(default=None, description="e.g. http://localhost:8003")
    ingestion_service_url: str | None = Field(default=None, description="e.g. http://localhost:8000")
    ingestion_s3_bucket: str = Field(default="versionai-ingestion", description="Ingestion S3 bucket")
    ingestion_s3_prefix: str = Field(default="uploads", description="Ingestion S3 key prefix")

    # --- Rate limiting ---
    rate_limit_requests_per_minute: int = Field(default=30, ge=1)

    # --- Security ---
    api_key: str | None = None
    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
