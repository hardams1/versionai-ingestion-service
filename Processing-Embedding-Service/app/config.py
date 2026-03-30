from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # --- Application ---
    app_name: str = "VersionAI Processing & Embedding Service"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    # --- Server (health/status API) ---
    host: str = "0.0.0.0"
    port: int = 8001

    # --- AWS / S3 ---
    aws_region: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    s3_bucket_name: str = "versionai-ingestion"
    s3_endpoint_url: str | None = None

    # --- SQS (consumer) ---
    sqs_queue_url: str | None = None
    sqs_endpoint_url: str | None = None
    sqs_max_messages: int = Field(default=5, ge=1, le=10)
    sqs_wait_time_seconds: int = Field(default=20, ge=0, le=20)
    sqs_visibility_timeout: int = Field(default=300, description="5 min default for processing")

    # --- Worker ---
    worker_concurrency: int = Field(default=3, ge=1, le=20)
    worker_shutdown_timeout: int = Field(default=30, description="Seconds to wait for graceful shutdown")

    # --- Text processing ---
    chunk_size: int = Field(default=512, description="Target tokens per chunk")
    chunk_overlap: int = Field(default=64, description="Overlap tokens between chunks")
    max_text_length: int = Field(default=5_000_000, description="Max characters before truncation")

    # --- Embeddings ---
    embedding_provider: Literal["openai", "sentence-transformers"] = "openai"
    openai_api_key: str | None = None
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int = 1536
    st_model_name: str = "all-MiniLM-L6-v2"

    # --- Vector store ---
    vector_store_provider: Literal["faiss", "pinecone"] = "faiss"
    faiss_index_dir: str = "./vector_store"
    pinecone_api_key: str | None = None
    pinecone_index_name: str = "versionai"
    pinecone_namespace: str = "default"

    # --- Local storage (reads files from ingestion service's local dir when S3 unavailable) ---
    local_storage_path: str | None = None

    # --- Idempotency / state ---
    state_db_path: str = "./state/processing.db"

    # --- Security ---
    api_key: str | None = None
    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
