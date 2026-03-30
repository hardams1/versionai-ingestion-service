from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from app.models.schemas import EmbeddingResult, TextChunk
from app.utils.exceptions import EmbeddingError

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)

_OPENAI_BATCH_LIMIT = 2048


class BaseEmbedder(ABC):
    @abstractmethod
    async def embed_chunks(self, chunks: list[TextChunk], metadata: dict | None = None) -> list[EmbeddingResult]:
        ...

    @property
    @abstractmethod
    def dimensions(self) -> int:
        ...


class OpenAIEmbedder(BaseEmbedder):
    """Generates embeddings via OpenAI's embedding API."""

    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key:
            raise EmbeddingError("OPENAI_API_KEY is required for OpenAI embeddings")

        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_embedding_model
        self._dimensions = settings.openai_embedding_dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed_chunks(self, chunks: list[TextChunk], metadata: dict | None = None) -> list[EmbeddingResult]:
        if not chunks:
            return []

        logger.info("Generating OpenAI embeddings for %d chunks (model=%s)", len(chunks), self._model)

        results: list[EmbeddingResult] = []

        for batch_start in range(0, len(chunks), _OPENAI_BATCH_LIMIT):
            batch = chunks[batch_start : batch_start + _OPENAI_BATCH_LIMIT]
            texts = [c.text for c in batch]

            try:
                response = await self._client.embeddings.create(
                    model=self._model,
                    input=texts,
                    dimensions=self._dimensions,
                )
            except Exception as exc:
                raise EmbeddingError(f"OpenAI embedding API error: {exc}") from exc

            for chunk, embedding_data in zip(batch, response.data):
                chunk_meta = dict(metadata) if metadata else {}
                chunk_meta.update(chunk.metadata)

                results.append(EmbeddingResult(
                    chunk_index=chunk.chunk_index,
                    vector=embedding_data.embedding,
                    text=chunk.text,
                    token_count=chunk.token_count,
                    metadata=chunk_meta,
                ))

        logger.info("Generated %d embeddings (%d dimensions)", len(results), self._dimensions)
        return results


class SentenceTransformerEmbedder(BaseEmbedder):
    """Local embeddings via sentence-transformers (no API key needed)."""

    def __init__(self, settings: Settings) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise EmbeddingError("sentence-transformers is required") from exc

        self._model_name = settings.st_model_name
        logger.info("Loading sentence-transformer model: %s", self._model_name)
        self._model = SentenceTransformer(self._model_name)
        self._dimensions = self._model.get_sentence_embedding_dimension()

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed_chunks(self, chunks: list[TextChunk], metadata: dict | None = None) -> list[EmbeddingResult]:
        if not chunks:
            return []

        logger.info("Generating local embeddings for %d chunks (model=%s)", len(chunks), self._model_name)

        texts = [c.text for c in chunks]
        loop = asyncio.get_event_loop()
        vectors = await loop.run_in_executor(None, lambda: self._model.encode(texts).tolist())

        results: list[EmbeddingResult] = []
        for chunk, vector in zip(chunks, vectors):
            chunk_meta = dict(metadata) if metadata else {}
            chunk_meta.update(chunk.metadata)

            results.append(EmbeddingResult(
                chunk_index=chunk.chunk_index,
                vector=vector,
                text=chunk.text,
                token_count=chunk.token_count,
                metadata=chunk_meta,
            ))

        logger.info("Generated %d embeddings (%d dimensions)", len(results), self._dimensions)
        return results
