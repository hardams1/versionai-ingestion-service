from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import Settings, get_settings
from app.services.embedder import (
    BaseQueryEmbedder,
    OpenAIQueryEmbedder,
    SentenceTransformerQueryEmbedder,
)
from app.services.llm import AnthropicLLM, BaseLLM, OpenAILLM
from app.services.memory import ConversationMemory
from app.services.personality_store import PersonalityStore
from app.services.prompt_builder import PromptBuilder
from app.services.retriever import BaseRetriever, FAISSRetriever, PineconeRetriever
from app.services.safety import SafetyProcessor
from app.services.integration import MediaClient
from app.services.orchestrator import BrainOrchestrator

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    settings: Settings = Depends(get_settings),
    api_key: str | None = Security(api_key_header),
) -> None:
    if settings.api_key is None:
        return
    if api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")


@lru_cache
def get_retriever() -> BaseRetriever:
    settings = get_settings()
    if settings.vector_store_provider == "pinecone":
        return PineconeRetriever(settings)
    return FAISSRetriever(settings)


@lru_cache
def get_query_embedder() -> BaseQueryEmbedder:
    settings = get_settings()
    if settings.embedding_provider == "openai":
        return OpenAIQueryEmbedder(settings)
    return SentenceTransformerQueryEmbedder(settings)


@lru_cache
def get_llm() -> BaseLLM:
    settings = get_settings()
    if settings.llm_provider == "anthropic":
        return AnthropicLLM(settings)
    return OpenAILLM(settings)


@lru_cache
def get_memory() -> ConversationMemory:
    return ConversationMemory(get_settings())


@lru_cache
def get_personality_store() -> PersonalityStore:
    return PersonalityStore(get_settings())


@lru_cache
def get_prompt_builder() -> PromptBuilder:
    return PromptBuilder(get_settings())


@lru_cache
def get_safety_processor() -> SafetyProcessor:
    return SafetyProcessor(get_settings())


@lru_cache
def get_media_client() -> MediaClient:
    return MediaClient(get_settings())


@lru_cache
def get_orchestrator() -> BrainOrchestrator:
    return BrainOrchestrator(
        settings=get_settings(),
        retriever=get_retriever(),
        embedder=get_query_embedder(),
        llm=get_llm(),
        memory=get_memory(),
        personality_store=get_personality_store(),
        prompt_builder=get_prompt_builder(),
        safety=get_safety_processor(),
        media_client=get_media_client(),
    )
