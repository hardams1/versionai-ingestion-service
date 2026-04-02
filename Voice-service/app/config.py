from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # --- Application ---
    app_name: str = "VersionAI Voice Service"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8003

    # --- TTS Provider (default engine; per-user profile overrides via registry) ---
    tts_provider: Literal["openai", "elevenlabs", "mock"] = "elevenlabs"

    # OpenAI TTS
    openai_api_key: str | None = None
    openai_tts_model: str = "tts-1"
    openai_tts_default_voice: str = "alloy"

    # ElevenLabs TTS (premium voice cloning)
    elevenlabs_api_key: str | None = None
    elevenlabs_model_id: str = "eleven_multilingual_v2"
    elevenlabs_default_voice_id: str | None = None

    # --- Audio output ---
    default_audio_format: Literal["mp3", "opus", "aac", "flac", "wav", "pcm"] = "mp3"
    default_sample_rate: int = Field(default=24000, description="Sample rate in Hz")
    max_text_length: int = Field(default=4096, description="Max characters per synthesis request")

    # --- Voice profiles ---
    voice_profile_storage: Literal["s3", "local"] = "local"
    voice_profiles_dir: str = "./voice_profiles"

    # S3 voice profile storage
    aws_region: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    s3_bucket_name: str = "versionai-voices"
    s3_endpoint_url: str | None = None
    s3_voice_profiles_prefix: str = "profiles"

    # --- Sibling services ---
    brain_service_url: str | None = Field(default=None, description="e.g. http://localhost:8002")

    # --- Rate limiting ---
    rate_limit_requests_per_minute: int = Field(default=60, ge=1)

    # --- Security ---
    api_key: str | None = None
    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
