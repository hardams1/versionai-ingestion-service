from __future__ import annotations

from unittest.mock import MagicMock

from app.services.chunker import TextChunker


def _make_settings(**overrides):
    settings = MagicMock()
    settings.chunk_size = overrides.get("chunk_size", 50)
    settings.chunk_overlap = overrides.get("chunk_overlap", 10)
    settings.openai_embedding_model = "text-embedding-3-small"
    return settings


class TestTextChunker:
    def test_short_text_single_chunk(self):
        chunker = TextChunker(_make_settings(chunk_size=500))
        text = "This is a short text."
        chunks = chunker.chunk(text)
        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].chunk_index == 0

    def test_empty_text(self):
        chunker = TextChunker(_make_settings())
        assert chunker.chunk("") == []
        assert chunker.chunk("   ") == []

    def test_long_text_splits(self, sample_text: str):
        chunker = TextChunker(_make_settings(chunk_size=50, chunk_overlap=10))
        chunks = chunker.chunk(sample_text)
        assert len(chunks) > 1
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
            assert chunk.text.strip() != ""
            assert chunk.token_count > 0

    def test_metadata_propagation(self):
        chunker = TextChunker(_make_settings(chunk_size=500))
        meta = {"ingestion_id": "test-123", "filename": "doc.txt"}
        chunks = chunker.chunk("Some test content", metadata=meta)
        assert len(chunks) == 1
        assert chunks[0].metadata["ingestion_id"] == "test-123"
        assert chunks[0].metadata["filename"] == "doc.txt"

    def test_chunk_offsets_valid(self, sample_text: str):
        chunker = TextChunker(_make_settings(chunk_size=80, chunk_overlap=0))
        chunks = chunker.chunk(sample_text)
        for chunk in chunks:
            assert chunk.start_char >= 0
            assert chunk.end_char > chunk.start_char
            assert chunk.end_char <= len(sample_text) + len(sample_text)
