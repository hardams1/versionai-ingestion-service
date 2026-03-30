from __future__ import annotations

import json
import os
import tempfile

import pytest

from app.services.retriever import FAISSRetriever


@pytest.fixture
def faiss_index_dir():
    """Create a temporary FAISS index with known data for testing."""
    import faiss
    import numpy as np

    tmpdir = tempfile.mkdtemp()
    dim = 4
    index = faiss.IndexFlatIP(dim)

    vectors = np.array([
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.5, 0.5, 0.0, 0.0],
    ], dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1
    vectors = vectors / norms
    index.add(vectors)

    metadata = [
        {"ingestion_id": "file-1", "chunk_index": 0, "text": "Document about cats.", "user_id": "user-a"},
        {"ingestion_id": "file-2", "chunk_index": 0, "text": "Document about dogs.", "user_id": "user-b"},
        {"ingestion_id": "file-3", "chunk_index": 0, "text": "Document about birds.", "user_id": "user-a"},
        {"ingestion_id": "file-4", "chunk_index": 0, "text": "Mixed topic.", "user_id": "user-a", "_deleted": True},
    ]
    id_map = {"file-1": [0], "file-2": [1], "file-3": [2], "file-4": [3]}

    faiss.write_index(index, os.path.join(tmpdir, "index.faiss"))
    with open(os.path.join(tmpdir, "metadata.json"), "w") as f:
        json.dump({"metadata": metadata, "id_map": id_map}, f)

    yield tmpdir


@pytest.fixture
def retriever_settings(settings, faiss_index_dir):
    settings.faiss_index_dir = faiss_index_dir
    return settings


@pytest.mark.asyncio
async def test_faiss_search_filters_by_user_id(retriever_settings):
    retriever = FAISSRetriever(retriever_settings)
    await retriever.initialize()

    query = [1.0, 0.0, 0.0, 0.0]
    results = await retriever.search(query, user_id="user-a", top_k=10, score_threshold=0.0)

    file_ids = {r.file_id for r in results}
    assert "file-2" not in file_ids  # belongs to user-b
    assert "file-1" in file_ids or "file-3" in file_ids


@pytest.mark.asyncio
async def test_faiss_search_excludes_deleted(retriever_settings):
    retriever = FAISSRetriever(retriever_settings)
    await retriever.initialize()

    query = [0.5, 0.5, 0.0, 0.0]
    results = await retriever.search(query, user_id="user-a", top_k=10, score_threshold=0.0)

    file_ids = {r.file_id for r in results}
    assert "file-4" not in file_ids  # deleted


@pytest.mark.asyncio
async def test_faiss_search_respects_score_threshold(retriever_settings):
    retriever = FAISSRetriever(retriever_settings)
    await retriever.initialize()

    query = [1.0, 0.0, 0.0, 0.0]
    results = await retriever.search(query, user_id="user-a", top_k=10, score_threshold=0.99)

    assert len(results) <= 1


@pytest.mark.asyncio
async def test_faiss_search_respects_top_k(retriever_settings):
    retriever = FAISSRetriever(retriever_settings)
    await retriever.initialize()

    query = [0.5, 0.5, 0.5, 0.0]
    results = await retriever.search(query, user_id="user-a", top_k=1, score_threshold=0.0)

    assert len(results) <= 1


@pytest.mark.asyncio
async def test_faiss_empty_index():
    import tempfile
    tmpdir = tempfile.mkdtemp()

    from app.config import Settings
    s = Settings(openai_api_key="sk-test", faiss_index_dir=tmpdir)
    retriever = FAISSRetriever(s)
    await retriever.initialize()

    results = await retriever.search([1.0, 0.0, 0.0, 0.0], user_id="user-a", top_k=5, score_threshold=0.0)
    assert results == []


@pytest.mark.asyncio
async def test_faiss_health_check(retriever_settings):
    retriever = FAISSRetriever(retriever_settings)
    await retriever.initialize()
    assert await retriever.health_check() is True


@pytest.mark.asyncio
async def test_faiss_health_check_no_index():
    import tempfile
    tmpdir = tempfile.mkdtemp()

    from app.config import Settings
    s = Settings(openai_api_key="sk-test", faiss_index_dir=tmpdir)
    retriever = FAISSRetriever(s)
    await retriever.initialize()
    assert await retriever.health_check() is False
