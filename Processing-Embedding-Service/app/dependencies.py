from __future__ import annotations

from functools import lru_cache

from app.config import Settings, get_settings
from app.services.chunker import TextChunker
from app.services.embedder import BaseEmbedder, OpenAIEmbedder, SentenceTransformerEmbedder
from app.services.processor import ProcessingOrchestrator
from app.services.queue_consumer import SQSConsumer
from app.services.storage import S3Fetcher
from app.services.text_cleaner import TextCleaner
from app.services.text_extractor import TextExtractor
from app.services.vector_store import BaseVectorStore, FAISSVectorStore, PineconeVectorStore
from app.utils.idempotency import StateStore


@lru_cache
def get_sqs_consumer() -> SQSConsumer:
    return SQSConsumer(get_settings())


@lru_cache
def get_s3_fetcher() -> S3Fetcher:
    return S3Fetcher(get_settings())


@lru_cache
def get_text_extractor() -> TextExtractor:
    return TextExtractor()


@lru_cache
def get_text_cleaner() -> TextCleaner:
    return TextCleaner()


@lru_cache
def get_chunker() -> TextChunker:
    return TextChunker(get_settings())


@lru_cache
def get_embedder() -> BaseEmbedder:
    settings = get_settings()
    if settings.embedding_provider == "openai":
        return OpenAIEmbedder(settings)
    return SentenceTransformerEmbedder(settings)


@lru_cache
def get_vector_store() -> BaseVectorStore:
    settings = get_settings()
    if settings.vector_store_provider == "pinecone":
        return PineconeVectorStore(settings)
    return FAISSVectorStore(settings)


@lru_cache
def get_state_store() -> StateStore:
    return StateStore(get_settings().state_db_path)


@lru_cache
def get_orchestrator() -> ProcessingOrchestrator:
    return ProcessingOrchestrator(
        settings=get_settings(),
        s3_fetcher=get_s3_fetcher(),
        text_extractor=get_text_extractor(),
        text_cleaner=get_text_cleaner(),
        chunker=get_chunker(),
        embedder=get_embedder(),
        vector_store=get_vector_store(),
        state_store=get_state_store(),
    )
