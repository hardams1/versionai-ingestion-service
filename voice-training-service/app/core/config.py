from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    app_name: str = "VersionAI Voice Training Service"
    port: int = 8008
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    database_url: str = "sqlite+aiosqlite:///./voice_training.db"

    jwt_secret_key: str = "versionai-dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"

    # ElevenLabs for voice cloning
    elevenlabs_api_key: Optional[str] = None
    elevenlabs_api_url: str = "https://api.elevenlabs.io/v1"

    # OpenAI for Whisper transcription + translation
    openai_api_key: Optional[str] = None

    # Voice Service URL (to update voice profiles)
    voice_service_url: str = "http://localhost:8003"

    # Audio constraints (ElevenLabs recommends 1-3 min for high-quality IVC)
    min_audio_duration_seconds: float = 90.0
    max_audio_duration_seconds: float = 600.0
    max_audio_file_size: int = 50 * 1024 * 1024  # 50MB

    # Storage
    audio_samples_dir: str = "./audio_samples"

    # Supported languages
    supported_languages: list[str] = [
        "en", "es", "fr", "ar", "zh", "hi", "pt", "bn", "ru", "ja", "yo", "pcm"
    ]

    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
