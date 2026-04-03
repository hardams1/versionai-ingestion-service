from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # --- Application ---
    app_name: str = "VersionAI Real-Time Orchestrator"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8005

    # --- Sibling service URLs ---
    brain_service_url: str = Field(
        default="http://localhost:8002",
        description="AI Brain Service (text generation)",
    )
    voice_service_url: str = Field(
        default="http://localhost:8003",
        description="Voice Service (TTS)",
    )
    video_avatar_service_url: str = Field(
        default="http://localhost:8004",
        description="Video Avatar Service (lip-sync video)",
    )
    profile_settings_service_url: str = Field(
        default="http://localhost:8007",
        description="Profile & Settings Service (output mode, preferences)",
    )
    voice_training_service_url: str = Field(
        default="http://localhost:8008",
        description="Voice Training Service (language detection, translation, voice cloning)",
    )
    stt_service_url: str = Field(
        default="http://localhost:8009",
        description="Speech-to-Text Service (Whisper transcription)",
    )
    social_graph_service_url: str = Field(
        default="http://localhost:8010",
        description="Social Graph Service (follow, access control, rate limiting)",
    )

    # --- Timeouts (seconds) ---
    brain_timeout: float = Field(default=30.0, description="Timeout for Brain chat call")
    voice_timeout: float = Field(default=120.0, description="Timeout for TTS synthesis")
    video_timeout: float = Field(default=120.0, description="Timeout for video rendering")
    health_check_timeout: float = Field(default=5.0, description="Timeout for service health checks")

    # --- Pipeline ---
    default_audio_format: str = "mp3"
    default_video_format: str = "mp4"
    max_query_length: int = Field(default=10000, ge=1)
    max_concurrent_sessions: int = Field(default=100, ge=1)

    # --- WebSocket ---
    ws_ping_interval: float = Field(default=20.0, description="WebSocket ping interval in seconds")
    ws_ping_timeout: float = Field(default=10.0, description="WebSocket ping response timeout")
    ws_max_message_size: int = Field(default=1024 * 1024, description="1 MB max incoming WS message")

    # --- Security ---
    api_key: str | None = None
    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
