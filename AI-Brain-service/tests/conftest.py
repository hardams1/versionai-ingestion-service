from __future__ import annotations

import os
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault("LLM_PROVIDER", "openai")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("VECTOR_STORE_PROVIDER", "faiss")
os.environ.setdefault("FAISS_INDEX_DIR", "/tmp/test_vector_store")
os.environ.setdefault("ENVIRONMENT", "development")


@pytest.fixture
def settings():
    from app.config import Settings

    return Settings(
        openai_api_key="sk-test-fake-key",
        faiss_index_dir="/tmp/test_vector_store",
        llm_timeout_seconds=10.0,
        llm_max_retries=1,
    )


@pytest.fixture
def mock_llm():
    from app.services.llm import LLMResponse
    from app.models.schemas import TokenUsage

    llm = AsyncMock()
    llm.model_name.return_value = "test-model"
    llm.generate.return_value = LLMResponse(
        content="This is a test response based on the provided context.",
        model="test-model",
        usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        finish_reason="stop",
    )
    return llm


@pytest.fixture
def mock_embedder():
    embedder = AsyncMock()
    embedder.embed.return_value = [0.1] * 1536
    return embedder


@pytest.fixture
def mock_retriever():
    from app.models.schemas import SourceChunk

    retriever = AsyncMock()
    retriever.search.return_value = [
        SourceChunk(
            text="Test context chunk about the topic.",
            score=0.85,
            file_id="test-file-1",
            chunk_index=0,
        ),
    ]
    retriever.health_check.return_value = True
    return retriever


@pytest.fixture
def mock_memory():
    from app.models.schemas import ConversationHistory

    memory = AsyncMock()
    memory.is_connected = True
    memory.redis_client = None
    memory.get_or_create.return_value = ConversationHistory(
        conversation_id="test-conv-123",
        user_id="test-user-1",
    )
    memory.get_history.return_value = []
    memory.add_turn.return_value = ConversationHistory(
        conversation_id="test-conv-123",
        user_id="test-user-1",
    )
    memory.health_check.return_value = True
    return memory


@pytest.fixture
def mock_personality_store():
    store = AsyncMock()
    store.get.return_value = None
    return store


@pytest.fixture
def orchestrator(settings, mock_retriever, mock_embedder, mock_llm, mock_memory, mock_personality_store):
    from app.services.orchestrator import BrainOrchestrator
    from app.services.prompt_builder import PromptBuilder
    from app.services.safety import SafetyProcessor

    return BrainOrchestrator(
        settings=settings,
        retriever=mock_retriever,
        embedder=mock_embedder,
        llm=mock_llm,
        memory=mock_memory,
        personality_store=mock_personality_store,
        prompt_builder=PromptBuilder(settings),
        safety=SafetyProcessor(settings),
    )
