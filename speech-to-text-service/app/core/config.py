from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    app_name: str = "VersionAI Speech-to-Text Service"
    port: int = 8009
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    jwt_secret_key: str = "versionai-dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"

    openai_api_key: Optional[str] = None
    whisper_model: str = "whisper-1"

    max_audio_file_size: int = 30 * 1024 * 1024  # 30 MB
    max_audio_duration_seconds: float = 300.0  # 5 minutes

    supported_languages: list[str] = [
        "en", "es", "fr", "ar", "zh", "hi", "pt", "bn", "ru", "ja", "yo", "pcm",
    ]

    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
