from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from app.models.enums import ProcessingPipeline, ProcessingStatus
from app.models.schemas import ProcessingRecord, QueueMessage
from app.services.text_cleaner import TextCleaner
from app.utils.exceptions import ProcessingError

if TYPE_CHECKING:
    from app.config import Settings
    from app.services.chunker import TextChunker
    from app.services.embedder import BaseEmbedder
    from app.services.storage import S3Fetcher
    from app.services.text_extractor import TextExtractor
    from app.services.vector_store import BaseVectorStore
    from app.utils.idempotency import StateStore

logger = logging.getLogger(__name__)


class ProcessingOrchestrator:
    """
    Orchestrates the full processing pipeline for a single message:
    download -> extract -> clean -> chunk -> embed -> store
    """

    def __init__(
        self,
        settings: Settings,
        s3_fetcher: S3Fetcher,
        text_extractor: TextExtractor,
        text_cleaner: TextCleaner,
        chunker: TextChunker,
        embedder: BaseEmbedder,
        vector_store: BaseVectorStore,
        state_store: StateStore,
    ) -> None:
        self._settings = settings
        self._s3 = s3_fetcher
        self._extractor = text_extractor
        self._cleaner = text_cleaner
        self._chunker = chunker
        self._embedder = embedder
        self._vector_store = vector_store
        self._state = state_store

    async def process(self, message: QueueMessage) -> ProcessingRecord:
        ingestion_id = message.ingestion_id
        start = time.monotonic()

        # Idempotency: skip if already completed
        if await self._state.is_processed(ingestion_id):
            logger.info("Skipping already-processed ingestion_id=%s", ingestion_id)
            record = await self._state.get_record(ingestion_id)
            if record:
                record.status = ProcessingStatus.SKIPPED
                return record
            return ProcessingRecord(
                ingestion_id=ingestion_id,
                status=ProcessingStatus.SKIPPED,
                file_category=message.file_category,
                filename=message.filename,
            )

        # Only process if EMBEDDING pipeline is requested
        if ProcessingPipeline.EMBEDDING not in message.pipelines:
            logger.info("EMBEDDING not in pipelines for %s – skipping", ingestion_id)
            return ProcessingRecord(
                ingestion_id=ingestion_id,
                status=ProcessingStatus.SKIPPED,
                file_category=message.file_category,
                filename=message.filename,
            )

        record = ProcessingRecord(
            ingestion_id=ingestion_id,
            status=ProcessingStatus.RECEIVED,
            file_category=message.file_category,
            filename=message.filename,
        )
        await self._state.upsert(record)

        file_path: Path | None = None
        try:
            # Step 1: Download from S3
            record.status = ProcessingStatus.DOWNLOADING
            await self._state.upsert(record)
            file_path = await self._s3.download(message.s3_bucket, message.s3_key)

            # Step 2: Extract text
            record.status = ProcessingStatus.EXTRACTING_TEXT
            await self._state.upsert(record)
            raw_text = await self._extractor.extract(
                file_path, message.file_category, message.mime_type
            )

            # Step 3: Clean and normalize
            record.status = ProcessingStatus.CLEANING
            await self._state.upsert(record)
            clean_text = self._cleaner.clean(raw_text, self._settings.max_text_length)

            if not clean_text.strip():
                raise ProcessingError("No text content after cleaning")

            # Step 4: Chunk
            record.status = ProcessingStatus.CHUNKING
            await self._state.upsert(record)
            chunk_metadata = {
                "ingestion_id": ingestion_id,
                "filename": message.filename,
                "file_category": message.file_category.value,
                **{k: v for k, v in message.metadata.items() if isinstance(v, (str, int, float, bool))},
            }
            chunks = self._chunker.chunk(clean_text, metadata=chunk_metadata)
            record.chunks_count = len(chunks)

            if not chunks:
                raise ProcessingError("Text produced zero chunks")

            # Step 5: Generate embeddings
            record.status = ProcessingStatus.EMBEDDING
            await self._state.upsert(record)
            embeddings = await self._embedder.embed_chunks(chunks, metadata=chunk_metadata)
            record.embeddings_count = len(embeddings)

            # Step 6: Store in vector database
            record.status = ProcessingStatus.STORING
            await self._state.upsert(record)
            stored = await self._vector_store.store(ingestion_id, embeddings)

            # Done
            elapsed = time.monotonic() - start
            record.status = ProcessingStatus.COMPLETED
            record.completed_at = datetime.now(timezone.utc)
            record.duration_seconds = round(elapsed, 2)
            record.embeddings_count = stored
            await self._state.upsert(record)

            logger.info(
                "Completed processing ingestion_id=%s: %d chunks, %d embeddings in %.2fs",
                ingestion_id, record.chunks_count, record.embeddings_count, elapsed,
            )
            return record

        except Exception as exc:
            elapsed = time.monotonic() - start
            record.status = ProcessingStatus.FAILED
            record.error_message = str(exc)[:2000]
            record.completed_at = datetime.now(timezone.utc)
            record.duration_seconds = round(elapsed, 2)
            await self._state.upsert(record)

            logger.exception("Failed to process ingestion_id=%s", ingestion_id)
            return record

        finally:
            if file_path and file_path.exists():
                file_path.unlink(missing_ok=True)
