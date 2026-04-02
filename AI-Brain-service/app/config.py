from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # --- Application ---
    app_name: str = "VersionAI AI Brain Service"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8002

    # --- LLM Provider ---
    llm_provider: Literal["openai", "anthropic"] = "openai"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"
    openai_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    openai_max_tokens: int = Field(default=1024, ge=1, le=16384)

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-20250514"
    anthropic_temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    anthropic_max_tokens: int = Field(default=1024, ge=1, le=8192)

    # --- LLM Reliability ---
    llm_timeout_seconds: float = Field(default=60.0, description="Timeout per LLM call")
    llm_max_retries: int = Field(default=3, ge=0, le=10)
    llm_retry_base_delay: float = Field(default=1.0, description="Base delay for exponential backoff")

    # --- Vector Store (read-only retrieval) ---
    vector_store_provider: Literal["faiss", "pinecone"] = "faiss"
    faiss_index_dir: str = "./vector_store"
    pinecone_api_key: str | None = None
    pinecone_index_name: str = "versionai"
    pinecone_namespace: str = "default"

    # --- Embedding (for query embedding before retrieval) ---
    embedding_provider: Literal["openai", "sentence-transformers"] = "openai"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int = 1536
    st_model_name: str = "all-MiniLM-L6-v2"

    # --- Retrieval ---
    retrieval_top_k: int = Field(default=5, ge=1, le=20)
    retrieval_score_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    retrieval_strict_tenant: bool = Field(
        default=False,
        description="If True, only return chunks that explicitly have the requesting user_id in metadata",
    )

    # --- Redis (conversation memory) ---
    redis_url: str = "redis://localhost:6379/0"
    memory_ttl_seconds: int = Field(default=3600, description="1 hour default TTL for conversations")
    memory_max_turns: int = Field(default=20, ge=1, le=100)

    # --- Safety ---
    safety_max_response_length: int = Field(default=4096, description="Max characters in final response")
    safety_block_patterns: list[str] = Field(default_factory=lambda: [
        r"(?i)\b(ssn|social\s+security)\b.*\d{3}[-\s]?\d{2}[-\s]?\d{4}",
        r"\b\d{16}\b",
        r"(?i)\b(password|secret|token)\s*[:=]\s*\S+",
    ])

    # --- Personality defaults ---
    default_system_prompt: str = (
        "You are a digital version of a real person. "
        "Speak naturally and conversationally, like a real human being. "
        "Never identify yourself as an AI, assistant, chatbot, or language model. "
        "If your identity data hasn't been uploaded yet, let the user know warmly."
    )

    # --- Sibling services (integration) ---
    ingestion_service_url: str | None = Field(default=None, description="e.g. http://localhost:8000")
    processing_service_url: str | None = Field(default=None, description="e.g. http://localhost:8001")
    voice_service_url: str | None = Field(default=None, description="e.g. http://localhost:8003")
    video_avatar_service_url: str | None = Field(default=None, description="e.g. http://localhost:8004")
    auth_service_url: str | None = Field(default="http://localhost:8006", description="Auth service for onboarding profiles")

    # --- Security ---
    api_key: str | None = None
    cors_origins: list[str] = ["*"]

    @field_validator("cors_origins")
    @classmethod
    def validate_cors(cls, v: list[str], info) -> list[str]:
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
