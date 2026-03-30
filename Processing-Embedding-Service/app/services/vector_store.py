from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from app.models.schemas import EmbeddingResult
from app.utils.exceptions import VectorStoreError

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


class BaseVectorStore(ABC):
    @abstractmethod
    async def store(self, ingestion_id: str, embeddings: list[EmbeddingResult]) -> int:
        """Store embeddings. Returns the number of vectors stored."""
        ...

    @abstractmethod
    async def delete(self, ingestion_id: str) -> int:
        """Delete all vectors for an ingestion_id. Returns count deleted."""
        ...

    @abstractmethod
    async def initialize(self) -> None:
        ...


class FAISSVectorStore(BaseVectorStore):
    """
    Local FAISS-based vector store for development and single-node deployments.
    Stores vectors in a FAISS index with metadata in a sidecar JSON file.
    """

    def __init__(self, settings: Settings) -> None:
        self._index_dir = Path(settings.faiss_index_dir)
        self._dimensions = settings.openai_embedding_dimensions
        self._index = None
        self._metadata: list[dict] = []
        self._id_map: dict[str, list[int]] = {}

    async def initialize(self) -> None:
        try:
            import faiss
        except ImportError as exc:
            raise VectorStoreError("faiss-cpu is required for FAISS vector store") from exc

        self._index_dir.mkdir(parents=True, exist_ok=True)

        index_path = self._index_dir / "index.faiss"
        meta_path = self._index_dir / "metadata.json"

        if index_path.exists() and meta_path.exists():
            logger.info("Loading existing FAISS index from %s", self._index_dir)
            self._index = faiss.read_index(str(index_path))
            with open(meta_path) as f:
                data = json.load(f)
            self._metadata = data.get("metadata", [])
            self._id_map = data.get("id_map", {})
        else:
            logger.info("Creating new FAISS index (dim=%d)", self._dimensions)
            self._index = faiss.IndexFlatIP(self._dimensions)
            self._metadata = []
            self._id_map = {}

    async def store(self, ingestion_id: str, embeddings: list[EmbeddingResult]) -> int:
        import numpy as np

        if not embeddings:
            return 0
        if self._index is None:
            raise VectorStoreError("FAISS index not initialized")

        vectors = np.array([e.vector for e in embeddings], dtype=np.float32)

        # L2-normalize for inner-product (cosine similarity) search
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1
        vectors = vectors / norms

        start_id = self._index.ntotal
        self._index.add(vectors)

        ids = list(range(start_id, start_id + len(embeddings)))
        self._id_map.setdefault(ingestion_id, []).extend(ids)

        for emb in embeddings:
            self._metadata.append({
                "ingestion_id": ingestion_id,
                "chunk_index": emb.chunk_index,
                "text": emb.text[:500],
                "token_count": emb.token_count,
                **{k: v for k, v in emb.metadata.items() if k != "text"},
            })

        self._persist()
        logger.info("Stored %d vectors for ingestion_id=%s (total=%d)", len(embeddings), ingestion_id, self._index.ntotal)
        return len(embeddings)

    async def delete(self, ingestion_id: str) -> int:
        """
        FAISS IndexFlatIP doesn't support deletion.
        We mark entries as deleted in metadata; a periodic rebuild can compact.
        """
        ids = self._id_map.pop(ingestion_id, [])
        for idx in ids:
            if idx < len(self._metadata):
                self._metadata[idx]["_deleted"] = True
        self._persist()
        return len(ids)

    def _persist(self) -> None:
        import faiss

        if self._index is None:
            return
        faiss.write_index(self._index, str(self._index_dir / "index.faiss"))
        with open(self._index_dir / "metadata.json", "w") as f:
            json.dump({"metadata": self._metadata, "id_map": self._id_map}, f)


class PineconeVectorStore(BaseVectorStore):
    """Production vector store backed by Pinecone."""

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.pinecone_api_key
        self._index_name = settings.pinecone_index_name
        self._namespace = settings.pinecone_namespace
        self._index = None

    async def initialize(self) -> None:
        if not self._api_key:
            raise VectorStoreError("PINECONE_API_KEY is required")

        try:
            from pinecone import Pinecone
        except ImportError as exc:
            raise VectorStoreError("pinecone-client is required") from exc

        pc = Pinecone(api_key=self._api_key)
        self._index = pc.Index(self._index_name)
        logger.info("Connected to Pinecone index: %s", self._index_name)

    async def store(self, ingestion_id: str, embeddings: list[EmbeddingResult]) -> int:
        if not embeddings or self._index is None:
            return 0

        vectors = []
        for emb in embeddings:
            vec_id = f"{ingestion_id}_{emb.chunk_index}"
            meta = {
                "ingestion_id": ingestion_id,
                "chunk_index": emb.chunk_index,
                "text": emb.text[:1000],
                "token_count": emb.token_count,
            }
            meta.update({k: v for k, v in emb.metadata.items() if isinstance(v, (str, int, float, bool))})
            vectors.append({"id": vec_id, "values": emb.vector, "metadata": meta})

        batch_size = 100
        total = 0
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i : i + batch_size]
            self._index.upsert(vectors=batch, namespace=self._namespace)
            total += len(batch)

        logger.info("Upserted %d vectors to Pinecone for ingestion_id=%s", total, ingestion_id)
        return total

    async def delete(self, ingestion_id: str) -> int:
        if self._index is None:
            return 0

        self._index.delete(
            filter={"ingestion_id": {"$eq": ingestion_id}},
            namespace=self._namespace,
        )
        logger.info("Deleted vectors for ingestion_id=%s from Pinecone", ingestion_id)
        return -1  # Pinecone doesn't return count
