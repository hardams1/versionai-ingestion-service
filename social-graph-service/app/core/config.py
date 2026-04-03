from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    app_name: str = "VersionAI Social Graph Service"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    host: str = "0.0.0.0"
    port: int = 8010

    database_url: str = "sqlite+aiosqlite:///./social_graph.db"

    jwt_secret_key: str = "versionai-dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"

    redis_url: str = "redis://localhost:6379/1"

    rate_limit_max_questions: int = 5
    rate_limit_window_seconds: int = 86400  # 24 hours

    profile_settings_service_url: str = "http://localhost:8007"
    auth_service_url: str = "http://localhost:8006"

    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
