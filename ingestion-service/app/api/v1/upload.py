from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, UploadFile, File

from app.config import Settings, get_settings
from app.dependencies import (
    get_file_validator,
    get_metadata_service,
    get_queue_publisher,
    get_storage_service,
    verify_api_key,
)
from app.models.enums import IngestionStatus
from app.models.schemas import QueueMessage, UploadBatchResponse, UploadResponse
from app.services.metadata import MetadataService
from app.services.queue import SQSPublisher
from app.services.storage import BaseStorageService
from app.services.validation import FileValidator
from app.utils.exceptions import QueuePublishError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"], dependencies=[Depends(verify_api_key)])


async def _ingest_single_file(
    file: UploadFile,
    settings: Settings,
    validator: FileValidator,
    storage: BaseStorageService,
    queue: SQSPublisher,
    meta_svc: MetadataService,
    user_id: str | None = None,
) -> UploadResponse:
    """Validate, store, and queue a single file with rollback on queue failure."""
    ingestion_id = str(uuid.uuid4())
    filename = file.filename or "unknown"

    file_bytes = await file.read()
    mime_type, category, checksum = validator.validate(filename, file_bytes)

    s3_key = await storage.upload(file_bytes, filename, category, mime_type, checksum)

    pipelines = meta_svc.resolve_pipelines(category)
    metadata = meta_svc.build_metadata(filename, mime_type, category, len(file_bytes), checksum)
    if user_id:
        metadata["user_id"] = user_id

    message = QueueMessage(
        ingestion_id=ingestion_id,
        filename=filename,
        s3_bucket=settings.s3_bucket_name,
        s3_key=s3_key,
        file_category=category,
        mime_type=mime_type,
        size_bytes=len(file_bytes),
        checksum_sha256=checksum,
        pipelines=pipelines,
        metadata=metadata,
    )

    try:
        await queue.publish(message)
    except QueuePublishError:
        logger.error(
            "Queue publish failed for ingestion_id=%s; rolling back stored file %s",
            ingestion_id, s3_key,
        )
        await storage.delete(s3_key)
        raise

    logger.info("Ingestion %s queued for file '%s'", ingestion_id, filename)

    return UploadResponse(
        ingestion_id=ingestion_id,
        filename=filename,
        file_category=category,
        size_bytes=len(file_bytes),
        mime_type=mime_type,
        s3_key=s3_key,
        status=IngestionStatus.QUEUED,
        pipelines=pipelines,
        created_at=datetime.now(timezone.utc),
    )


@router.post(
    "/",
    response_model=UploadResponse,
    status_code=201,
    summary="Upload a single file for ingestion",
)
async def upload_file(
    file: UploadFile = File(..., description="The file to upload"),
    user_id: str | None = Form(default=None, description="Owner user ID for tenant isolation"),
    settings: Settings = Depends(get_settings),
    validator: FileValidator = Depends(get_file_validator),
    storage: BaseStorageService = Depends(get_storage_service),
    queue: SQSPublisher = Depends(get_queue_publisher),
    meta_svc: MetadataService = Depends(get_metadata_service),
) -> UploadResponse:
    return await _ingest_single_file(file, settings, validator, storage, queue, meta_svc, user_id=user_id)


@router.post(
    "/batch",
    response_model=UploadBatchResponse,
    status_code=201,
    summary="Upload multiple files for ingestion",
)
async def upload_batch(
    files: list[UploadFile] = File(..., description="Files to upload"),
    user_id: str | None = Form(default=None, description="Owner user ID for tenant isolation"),
    settings: Settings = Depends(get_settings),
    validator: FileValidator = Depends(get_file_validator),
    storage: BaseStorageService = Depends(get_storage_service),
    queue: SQSPublisher = Depends(get_queue_publisher),
    meta_svc: MetadataService = Depends(get_metadata_service),
) -> UploadBatchResponse:
    results: list[UploadResponse] = []

    for file in files:
        result = await _ingest_single_file(file, settings, validator, storage, queue, meta_svc, user_id=user_id)
        results.append(result)

    logger.info("Batch upload complete: %d files queued", len(results))
    return UploadBatchResponse(files=results, total=len(results))
