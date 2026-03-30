from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.models.enums import FileCategory, ProcessingPipeline, ProcessingStatus


class QueueMessage(BaseModel):
    """Mirrors the ingestion service's QueueMessage — the integration contract."""
    ingestion_id: str
    filename: str
    s3_bucket: str
    s3_key: str
    file_category: FileCategory
    mime_type: str
    size_bytes: int
    checksum_sha256: str
    pipelines: list[ProcessingPipeline]
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SimplifiedMessage(BaseModel):
    """Alternative input format per spec: {file_id, user_id, file_type, s3_url, processing_steps}."""
    file_id: str
    user_id: str
    file_type: FileCategory
    s3_url: str
    processing_steps: list[str] = Field(default_factory=list)


class TextChunk(BaseModel):
    chunk_index: int
    text: str
    token_count: int
    start_char: int
    end_char: int
    metadata: dict = Field(default_factory=dict)


class EmbeddingResult(BaseModel):
    chunk_index: int
    vector: list[float]
    text: str
    token_count: int
    metadata: dict = Field(default_factory=dict)


class ProcessingRecord(BaseModel):
    ingestion_id: str
    status: ProcessingStatus
    file_category: FileCategory
    filename: str
    chunks_count: int = 0
    embeddings_count: int = 0
    error_message: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    duration_seconds: float | None = None


class ErrorDetail(BaseModel):
    detail: str
    code: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    environment: str
    worker_running: bool = False
    messages_processed: int = 0


class ProcessingStatusResponse(BaseModel):
    ingestion_id: str
    status: ProcessingStatus
    chunks_count: int = 0
    embeddings_count: int = 0
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None
