from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from app.utils.exceptions import RetrievalError

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


class BaseQueryEmbedder(ABC):
    """Embeds the user query so we can search the vector store."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]: ...


class OpenAIQueryEmbedder(BaseQueryEmbedder):
    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key:
            raise RetrievalError("OPENAI_API_KEY is required for OpenAI embeddings")

        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RetrievalError("openai package is required") from exc

        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=30.0,
        )
        self._model = settings.openai_embedding_model
        self._dimensions = settings.openai_embedding_dimensions

    async def embed(self, text: str) -> list[float]:
        try:
            response = await asyncio.wait_for(
                self._client.embeddings.create(
                    input=[text],
                    model=self._model,
                    dimensions=self._dimensions,
                ),
                timeout=30.0,
            )
            return response.data[0].embedding
        except asyncio.TimeoutError as exc:
            raise RetrievalError("Embedding request timed out after 30s") from exc
        except Exception as exc:
            logger.exception("OpenAI embedding failed")
            raise RetrievalError(f"Embedding error: {exc}") from exc


class SentenceTransformerQueryEmbedder(BaseQueryEmbedder):
    def __init__(self, settings: Settings) -> None:
        self._model_name = settings.st_model_name
        self._model = None

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RetrievalError("sentence-transformers is required") from exc
            self._model = SentenceTransformer(self._model_name)
            logger.info("Loaded SentenceTransformer model: %s", self._model_name)
        return self._model

    async def embed(self, text: str) -> list[float]:
        """Run model.encode in a thread executor to avoid blocking the event loop."""
        model = self._load_model()
        loop = asyncio.get_running_loop()
        embedding = await loop.run_in_executor(
            None, lambda: model.encode(text, normalize_embeddings=True)
        )
        return embedding.tolist()
