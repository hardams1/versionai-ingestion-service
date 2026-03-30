from __future__ import annotations

import json
import logging
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from app.models.schemas import SourceChunk
from app.utils.exceptions import RetrievalError

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


class BaseRetriever(ABC):
    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    async def search(
        self, query_vector: list[float], user_id: str, top_k: int, score_threshold: float
    ) -> list[SourceChunk]: ...

    async def health_check(self) -> bool:
        return True


class FAISSRetriever(BaseRetriever):
    """
    Read-only FAISS search against the index built by the Processing Service.
    Filters results by user_id to enforce multi-tenant isolation.
    """

    def __init__(self, settings: Settings) -> None:
        self._index_dir = Path(settings.faiss_index_dir)
        self._index = None
        self._metadata: list[dict] = []
        self._id_map: dict[str, list[int]] = {}
        self._lock = threading.Lock()
        self._last_ntotal = -1
        self._strict_tenant = settings.retrieval_strict_tenant

    async def initialize(self) -> None:
        try:
            import faiss  # noqa: F401
        except ImportError as exc:
            raise RetrievalError("faiss-cpu is required for FAISS retrieval") from exc

        self._load_index()

    def _load_index(self) -> None:
        import faiss

        index_path = self._index_dir / "index.faiss"
        meta_path = self._index_dir / "metadata.json"

        if index_path.exists() and meta_path.exists():
            with self._lock:
                self._index = faiss.read_index(str(index_path))
                with open(meta_path) as f:
                    data = json.load(f)
                self._metadata = data.get("metadata", [])
                self._id_map = data.get("id_map", {})
                self._last_ntotal = self._index.ntotal
            logger.info(
                "FAISS index loaded: %d vectors, %d metadata entries",
                self._index.ntotal,
                len(self._metadata),
            )
        else:
            logger.warning("No FAISS index found at %s — retrieval will return empty results", self._index_dir)

    def _reload_if_changed(self) -> None:
        """Atomic hot-reload: read index under lock to prevent torn reads."""
        import faiss

        index_path = self._index_dir / "index.faiss"
        meta_path = self._index_dir / "metadata.json"
        if not index_path.exists() or not meta_path.exists():
            return

        try:
            new_index = faiss.read_index(str(index_path))
        except Exception:
            logger.warning("Failed to read FAISS index for reload — keeping current index")
            return

        if new_index.ntotal != self._last_ntotal:
            try:
                with open(meta_path) as f:
                    data = json.load(f)
                with self._lock:
                    self._index = new_index
                    self._metadata = data.get("metadata", [])
                    self._id_map = data.get("id_map", {})
                    self._last_ntotal = new_index.ntotal
                logger.info("FAISS index reloaded: %d vectors", new_index.ntotal)
            except Exception:
                logger.warning("Failed to reload FAISS metadata — keeping current state")

    async def search(
        self, query_vector: list[float], user_id: str, top_k: int, score_threshold: float
    ) -> list[SourceChunk]:
        import numpy as np

        self._reload_if_changed()

        if self._index is None or self._index.ntotal == 0:
            return []

        query = np.array([query_vector], dtype=np.float32)
        norms = np.linalg.norm(query, axis=1, keepdims=True)
        norms[norms == 0] = 1
        query = query / norms

        fetch_k = min(top_k * 5, self._index.ntotal)
        scores, indices = self._index.search(query, fetch_k)

        results: list[SourceChunk] = []
        for score, idx in zip(scores[0], indices[0]):
            if len(results) >= top_k:
                break
            if idx < 0 or idx >= len(self._metadata):
                continue
            if float(score) < score_threshold:
                continue

            meta = self._metadata[idx]
            if meta.get("_deleted"):
                continue

            chunk_user = meta.get("user_id")
            if chunk_user and chunk_user != user_id:
                continue
            if self._strict_tenant and not chunk_user:
                continue

            results.append(SourceChunk(
                text=meta.get("text", ""),
                score=round(float(score), 4),
                file_id=meta.get("ingestion_id"),
                chunk_index=meta.get("chunk_index"),
                metadata={
                    k: v for k, v in meta.items()
                    if k not in ("text", "_deleted", "ingestion_id", "chunk_index", "user_id")
                },
            ))

        logger.info(
            "FAISS search: user=%s, returned=%d (fetched=%d, top_k=%d, threshold=%.2f)",
            user_id, len(results), fetch_k, top_k, score_threshold,
        )
        return results

    async def health_check(self) -> bool:
        return self._index is not None


class PineconeRetriever(BaseRetriever):
    """Production retriever backed by Pinecone with user_id namespace isolation."""

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.pinecone_api_key
        self._index_name = settings.pinecone_index_name
        self._namespace = settings.pinecone_namespace
        self._index = None

    async def initialize(self) -> None:
        if not self._api_key:
            raise RetrievalError("PINECONE_API_KEY is required")

        try:
            from pinecone import Pinecone
        except ImportError as exc:
            raise RetrievalError("pinecone-client is required") from exc

        pc = Pinecone(api_key=self._api_key)
        self._index = pc.Index(self._index_name)
        logger.info("Connected to Pinecone index: %s", self._index_name)

    async def search(
        self, query_vector: list[float], user_id: str, top_k: int, score_threshold: float
    ) -> list[SourceChunk]:
        if self._index is None:
            return []

        try:
            response = self._index.query(
                vector=query_vector,
                top_k=top_k,
                include_metadata=True,
                namespace=self._namespace,
                filter={"user_id": {"$eq": user_id}},
            )
        except Exception as exc:
            logger.exception("Pinecone query failed")
            raise RetrievalError(f"Pinecone query error: {exc}") from exc

        matches = getattr(response, "matches", None) or []

        results: list[SourceChunk] = []
        for match in matches:
            match_score = getattr(match, "score", 0.0)
            if match_score < score_threshold:
                continue

            meta = getattr(match, "metadata", {}) or {}
            results.append(SourceChunk(
                text=meta.get("text", ""),
                score=round(float(match_score), 4),
                file_id=meta.get("ingestion_id"),
                chunk_index=meta.get("chunk_index"),
                metadata={
                    k: v for k, v in meta.items()
                    if k not in ("text", "ingestion_id", "chunk_index", "user_id")
                },
            ))

        logger.info("Pinecone search: user=%s, returned=%d", user_id, len(results))
        return results

    async def health_check(self) -> bool:
        return self._index is not None
