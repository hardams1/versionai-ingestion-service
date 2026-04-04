from __future__ import annotations

from functools import lru_cache
from typing import List, Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    app_name: str = "VersionAI Feedback Intelligence Service"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    host: str = "0.0.0.0"
    port: int = 8011

    database_url: str = "sqlite+aiosqlite:///./feedback.db"

    jwt_secret_key: str = "versionai-dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"

    redis_url: str = "redis://localhost:6379/2"
    ranking_cache_ttl: int = Field(default=300, description="Ranking cache TTL in seconds")

    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    categorization_timeout: float = 15.0

    default_categories: List[str] = Field(default_factory=lambda: [
        "Personal Life",
        "Career",
        "Relationships",
        "Finance",
        "Beliefs",
        "Education",
        "Health",
        "Hobbies",
        "Travel",
        "Misc",
    ])

    cors_origins: List[str] = ["*"]

    brain_service_url: str = "http://localhost:8002"


@lru_cache
def get_settings() -> Settings:
    return Settings()
