from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.models.enums import FileCategory, IngestionStatus, ProcessingPipeline


# ---------------------------------------------------------------------------
# Upload response
# ---------------------------------------------------------------------------

class UploadResponse(BaseModel):
    ingestion_id: str = Field(description="Unique ingestion tracking ID")
    filename: str
    file_category: FileCategory
    size_bytes: int
    mime_type: str
    s3_key: str
    status: IngestionStatus
    pipelines: list[ProcessingPipeline]
    created_at: datetime


class UploadBatchResponse(BaseModel):
    files: list[UploadResponse]
    total: int


# ---------------------------------------------------------------------------
# Queue message payload
# ---------------------------------------------------------------------------

class QueueMessage(BaseModel):
    ingestion_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
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


# ---------------------------------------------------------------------------
# Health / Status
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    environment: str


class ErrorDetail(BaseModel):
    detail: str
    code: str | None = None
