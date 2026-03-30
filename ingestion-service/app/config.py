from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # --- Application ---
    app_name: str = "VersionAI Ingestion Service"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000

    # --- Upload constraints ---
    max_upload_size_bytes: int = Field(default=500 * 1024 * 1024, description="500 MB default")
    allowed_mime_types: list[str] = Field(default=[
        # Video
        "video/mp4", "video/quicktime", "video/x-msvideo", "video/webm", "video/x-matroska",
        # Audio
        "audio/mpeg", "audio/wav", "audio/ogg", "audio/flac", "audio/x-wav", "audio/mp4",
        # Text
        "text/plain", "text/csv", "text/markdown",
        # PDF
        "application/pdf",
        # Documents
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ])

    # --- AWS / S3 ---
    aws_region: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    s3_bucket_name: str = "versionai-ingestion"
    s3_endpoint_url: str | None = None  # for MinIO / LocalStack
    s3_prefix: str = "uploads"

    # --- SQS ---
    sqs_queue_url: str | None = None
    sqs_endpoint_url: str | None = None  # for LocalStack

    # --- Processing service webhook (used when SQS is unavailable) ---
    processing_webhook_url: str | None = None

    # --- Local storage (fallback when S3 is unavailable) ---
    use_local_storage: bool = True
    local_storage_path: str = "./storage"

    # --- Security ---
    api_key: str | None = None  # optional API-key gating
    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
