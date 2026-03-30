"""
End-to-end integration test: exercises the full processing pipeline.
S3 download is mocked (aioboto3+moto async compat issue), but all other steps
run for real: extract -> clean -> chunk -> embed (sentence-transformers) -> FAISS store.
"""
from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.config import Settings
from app.models.enums import FileCategory, ProcessingPipeline, ProcessingStatus
from app.models.schemas import QueueMessage
from app.services.chunker import TextChunker
from app.services.embedder import SentenceTransformerEmbedder
from app.services.processor import ProcessingOrchestrator
from app.services.storage import S3Fetcher
from app.services.text_cleaner import TextCleaner
from app.services.text_extractor import TextExtractor
from app.services.vector_store import FAISSVectorStore
from app.utils.idempotency import StateStore

SAMPLE_TEXT = """
Artificial intelligence is transforming every industry.
Machine learning models can now generate text, images, and code.
The rise of large language models has sparked a new wave of innovation.

Natural language processing enables computers to understand human language.
Embeddings represent text as numerical vectors for semantic search.
Vector databases store these embeddings for fast similarity retrieval.

Deep learning uses neural networks with many layers to learn representations.
Transformers are the architecture behind modern language models like GPT and BERT.
Attention mechanisms allow models to focus on relevant parts of the input.
"""


@pytest.fixture
def settings(tmp_path):
    return Settings(
        environment="development",
        aws_region="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        s3_bucket_name="test-bucket",
        embedding_provider="sentence-transformers",
        st_model_name="all-MiniLM-L6-v2",
        vector_store_provider="faiss",
        faiss_index_dir=str(tmp_path / "faiss"),
        state_db_path=str(tmp_path / "state" / "test.db"),
        chunk_size=80,
        chunk_overlap=15,
        max_text_length=5_000_000,
        openai_embedding_model="text-embedding-3-small",
        openai_embedding_dimensions=384,
    )


def _write_temp_file(content: str, suffix: str = ".txt") -> Path:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, mode="w")
    tmp.write(content)
    tmp.close()
    return Path(tmp.name)


async def _build_pipeline(settings, tmp_text_path: Path | None = None):
    """Build orchestrator with a mock S3 fetcher that returns a local file."""
    s3_fetcher = AsyncMock(spec=S3Fetcher)
    if tmp_text_path:
        s3_fetcher.download.return_value = tmp_text_path

    text_extractor = TextExtractor()
    text_cleaner = TextCleaner()
    chunker = TextChunker(settings)
    embedder = SentenceTransformerEmbedder(settings)
    vector_store = FAISSVectorStore(settings)
    state_store = StateStore(settings.state_db_path)

    await state_store.initialize()
    await vector_store.initialize()

    orchestrator = ProcessingOrchestrator(
        settings=settings,
        s3_fetcher=s3_fetcher,
        text_extractor=text_extractor,
        text_cleaner=text_cleaner,
        chunker=chunker,
        embedder=embedder,
        vector_store=vector_store,
        state_store=state_store,
    )
    return orchestrator, state_store, vector_store


def _make_message(ingestion_id: str = "e2e-001", **overrides) -> QueueMessage:
    defaults = dict(
        ingestion_id=ingestion_id,
        filename="sample.txt",
        s3_bucket="test-bucket",
        s3_key="uploads/sample.txt",
        file_category=FileCategory.TEXT,
        mime_type="text/plain",
        size_bytes=len(SAMPLE_TEXT),
        checksum_sha256="abc123",
        pipelines=[ProcessingPipeline.EMBEDDING],
        metadata={"user_id": "test-user"},
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return QueueMessage(**defaults)


@pytest.mark.asyncio
async def test_full_pipeline_text_file(settings):
    """Complete pipeline: download(mock) -> extract -> clean -> chunk -> embed -> FAISS store."""
    tmp_file = _write_temp_file(SAMPLE_TEXT)
    try:
        orchestrator, state_store, _ = await _build_pipeline(settings, tmp_file)
        message = _make_message()

        record = await orchestrator.process(message)

        assert record.status == ProcessingStatus.COMPLETED, f"Expected COMPLETED, got {record.status}: {record.error_message}"
        assert record.chunks_count > 0
        assert record.embeddings_count > 0
        assert record.duration_seconds is not None
        assert record.duration_seconds > 0
        assert record.error_message is None

        # FAISS index was persisted
        faiss_dir = Path(settings.faiss_index_dir)
        assert (faiss_dir / "index.faiss").exists()
        assert (faiss_dir / "metadata.json").exists()

        await state_store.close()
    finally:
        tmp_file.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_idempotency(settings):
    """Second processing of the same ingestion_id should be skipped."""
    tmp_file = _write_temp_file(SAMPLE_TEXT)
    try:
        orchestrator, state_store, _ = await _build_pipeline(settings, tmp_file)
        message = _make_message(ingestion_id="idempotency-test")

        record1 = await orchestrator.process(message)
        assert record1.status == ProcessingStatus.COMPLETED

        # Create a new temp file for second run (first gets cleaned up by orchestrator)
        tmp_file2 = _write_temp_file(SAMPLE_TEXT)
        orchestrator._s3.download.return_value = tmp_file2

        record2 = await orchestrator.process(message)
        assert record2.status == ProcessingStatus.SKIPPED

        await state_store.close()
    finally:
        tmp_file.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_pipeline_skips_non_embedding(settings):
    """Messages without EMBEDDING pipeline should be skipped immediately."""
    orchestrator, state_store, _ = await _build_pipeline(settings)
    message = _make_message(
        ingestion_id="skip-test",
        pipelines=[ProcessingPipeline.TRANSCRIPTION, ProcessingPipeline.FRAME_EXTRACTION],
    )

    record = await orchestrator.process(message)
    assert record.status == ProcessingStatus.SKIPPED

    # S3 should never have been called
    orchestrator._s3.download.assert_not_called()

    await state_store.close()


@pytest.mark.asyncio
async def test_pipeline_handles_extraction_failure(settings):
    """If text extraction fails, the record should show FAILED with error details."""
    empty_file = _write_temp_file("")
    try:
        orchestrator, state_store, _ = await _build_pipeline(settings, empty_file)
        message = _make_message(ingestion_id="fail-test")

        record = await orchestrator.process(message)

        assert record.status == ProcessingStatus.FAILED
        assert record.error_message is not None

        # Verify it was persisted
        stored = await state_store.get_record("fail-test")
        assert stored is not None
        assert stored.status == ProcessingStatus.FAILED

        await state_store.close()
    finally:
        empty_file.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_status_api_after_processing(settings):
    """State store should correctly track and report processing records."""
    tmp_file = _write_temp_file("Short text for testing the status tracking API.")
    try:
        orchestrator, state_store, _ = await _build_pipeline(settings, tmp_file)
        message = _make_message(ingestion_id="status-test")

        await orchestrator.process(message)

        # Check individual record
        record = await state_store.get_record("status-test")
        assert record is not None
        assert record.status == ProcessingStatus.COMPLETED

        # Check listing
        records = await state_store.list_recent(10)
        assert len(records) >= 1
        assert any(r.ingestion_id == "status-test" for r in records)

        # Check counts
        counts = await state_store.count_by_status()
        assert counts.get("completed", 0) >= 1

        await state_store.close()
    finally:
        tmp_file.unlink(missing_ok=True)
