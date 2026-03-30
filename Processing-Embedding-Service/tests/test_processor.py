from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import FileCategory, ProcessingPipeline, ProcessingStatus
from app.models.schemas import EmbeddingResult, QueueMessage, TextChunk
from app.services.processor import ProcessingOrchestrator


def _make_message(**overrides) -> QueueMessage:
    defaults = {
        "ingestion_id": "test-ingestion-001",
        "filename": "test.txt",
        "s3_bucket": "test-bucket",
        "s3_key": "uploads/test.txt",
        "file_category": FileCategory.TEXT,
        "mime_type": "text/plain",
        "size_bytes": 1000,
        "checksum_sha256": "abc123",
        "pipelines": [ProcessingPipeline.EMBEDDING],
        "metadata": {"user_id": "user-1"},
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return QueueMessage(**defaults)


def _make_chunks(n: int = 3) -> list[TextChunk]:
    return [
        TextChunk(chunk_index=i, text=f"Chunk {i} text content", token_count=10, start_char=i * 100, end_char=(i + 1) * 100)
        for i in range(n)
    ]


def _make_embeddings(n: int = 3) -> list[EmbeddingResult]:
    return [
        EmbeddingResult(chunk_index=i, vector=[0.1] * 10, text=f"Chunk {i}", token_count=10)
        for i in range(n)
    ]


@pytest.fixture
def mock_services():
    settings = MagicMock()
    settings.max_text_length = 5_000_000

    s3_fetcher = AsyncMock()
    text_extractor = AsyncMock()
    text_cleaner = MagicMock()
    chunker = MagicMock()
    embedder = AsyncMock()
    vector_store = AsyncMock()
    state_store = AsyncMock()

    state_store.is_processed.return_value = False
    state_store.upsert.return_value = None

    return {
        "settings": settings,
        "s3_fetcher": s3_fetcher,
        "text_extractor": text_extractor,
        "text_cleaner": text_cleaner,
        "chunker": chunker,
        "embedder": embedder,
        "vector_store": vector_store,
        "state_store": state_store,
    }


@pytest.mark.asyncio
async def test_process_success(mock_services):
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        tmp.write(b"Hello world")
        tmp_path = Path(tmp.name)

    mock_services["s3_fetcher"].download.return_value = tmp_path
    mock_services["text_extractor"].extract.return_value = "Hello world extracted text"
    mock_services["text_cleaner"].clean.return_value = "Hello world cleaned text"
    mock_services["chunker"].chunk.return_value = _make_chunks(2)
    mock_services["embedder"].embed_chunks.return_value = _make_embeddings(2)
    mock_services["vector_store"].store.return_value = 2

    orchestrator = ProcessingOrchestrator(**mock_services)
    msg = _make_message()
    record = await orchestrator.process(msg)

    assert record.status == ProcessingStatus.COMPLETED
    assert record.chunks_count == 2
    assert record.embeddings_count == 2
    assert record.duration_seconds is not None

    mock_services["s3_fetcher"].download.assert_called_once()
    mock_services["text_extractor"].extract.assert_called_once()
    mock_services["vector_store"].store.assert_called_once()


@pytest.mark.asyncio
async def test_process_skips_already_processed(mock_services):
    mock_services["state_store"].is_processed.return_value = True
    mock_services["state_store"].get_record.return_value = MagicMock(
        status=ProcessingStatus.COMPLETED,
    )

    orchestrator = ProcessingOrchestrator(**mock_services)
    record = await orchestrator.process(_make_message())

    assert record.status == ProcessingStatus.SKIPPED
    mock_services["s3_fetcher"].download.assert_not_called()


@pytest.mark.asyncio
async def test_process_skips_non_embedding_pipeline(mock_services):
    msg = _make_message(pipelines=[ProcessingPipeline.TRANSCRIPTION])
    orchestrator = ProcessingOrchestrator(**mock_services)
    record = await orchestrator.process(msg)

    assert record.status == ProcessingStatus.SKIPPED
    mock_services["s3_fetcher"].download.assert_not_called()


@pytest.mark.asyncio
async def test_process_handles_extraction_failure(mock_services):
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        tmp.write(b"data")
        tmp_path = Path(tmp.name)

    mock_services["s3_fetcher"].download.return_value = tmp_path
    mock_services["text_extractor"].extract.side_effect = Exception("Extraction failed")

    orchestrator = ProcessingOrchestrator(**mock_services)
    record = await orchestrator.process(_make_message())

    assert record.status == ProcessingStatus.FAILED
    assert "Extraction failed" in record.error_message
