from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    app_name: str = "VersionAI Notification Service"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    host: str = "0.0.0.0"
    port: int = 8013

    database_path: str = "./notifications.db"

    jwt_secret_key: str = "versionai-dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"

    social_graph_service_url: str = "http://localhost:8010"
    feedback_intelligence_service_url: str = "http://localhost:8011"
    social_ingestion_service_url: str = "http://localhost:8012"
    voice_training_service_url: str = "http://localhost:8008"
    ai_brain_service_url: str = "http://localhost:8002"

    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
