from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.models.schemas import (
    ChatResponse,
    ConversationHistory,
    MemoryStatusResponse,
    PersonalityConfig,
    SourceChunk,
    TokenUsage,
)
from app.models.enums import SafetyVerdict
from app.services.llm import LLMResponse


@pytest.fixture
def client():
    """
    Build a TestClient with all dependencies overridden via FastAPI's system.
    This avoids real LLM/Redis/FAISS calls.
    """
    from app.main import app
    from app import dependencies

    mock_orchestrator = AsyncMock()
    mock_orchestrator.chat.return_value = ChatResponse(
        conversation_id="conv-1",
        response="Hello from the brain!",
        sources=[SourceChunk(text="context", score=0.9, file_id="f1", chunk_index=0)],
        safety_verdict=SafetyVerdict.PASS,
        model_used="test-model",
        usage=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        latency_ms=42.0,
    )

    mock_memory = AsyncMock()
    mock_memory.is_connected = True
    mock_memory.redis_client = None
    mock_memory.health_check.return_value = True
    mock_memory.get_history.return_value = []
    mock_memory.get_status.return_value = None
    mock_memory.delete.return_value = False

    mock_retriever = AsyncMock()
    mock_retriever.health_check.return_value = True

    mock_personality_store = AsyncMock()
    mock_personality_store.get.return_value = None
    mock_personality_store.list_for_user.return_value = []
    mock_personality_store.delete.return_value = False

    app.dependency_overrides[dependencies.get_orchestrator] = lambda: mock_orchestrator
    app.dependency_overrides[dependencies.get_memory] = lambda: mock_memory
    app.dependency_overrides[dependencies.get_retriever] = lambda: mock_retriever
    app.dependency_overrides[dependencies.get_personality_store] = lambda: mock_personality_store

    test_client = TestClient(app, raise_server_exceptions=False)

    yield {
        "client": test_client,
        "orchestrator": mock_orchestrator,
        "memory": mock_memory,
        "retriever": mock_retriever,
        "personality_store": mock_personality_store,
    }

    app.dependency_overrides.clear()


def test_root(client):
    resp = client["client"].get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "service" in data
    assert "version" in data


def test_health(client):
    resp = client["client"].get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert "dependencies" in data


def test_chat_endpoint(client):
    resp = client["client"].post("/api/v1/chat/", json={
        "user_id": "user-1",
        "query": "What is AI?",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["conversation_id"] == "conv-1"
    assert data["response"] == "Hello from the brain!"
    assert len(data["sources"]) == 1
    client["orchestrator"].chat.assert_called_once()


def test_chat_endpoint_validation_error(client):
    resp = client["client"].post("/api/v1/chat/", json={"user_id": "", "query": "test"})
    assert resp.status_code == 422


def test_chat_endpoint_missing_query(client):
    resp = client["client"].post("/api/v1/chat/", json={"user_id": "u1"})
    assert resp.status_code == 422


def test_personality_create(client):
    test_config = PersonalityConfig(
        personality_id="p-1",
        user_id="user-1",
        system_prompt="Be a pirate.",
    )
    client["personality_store"].save.return_value = test_config

    resp = client["client"].post("/api/v1/personality/", json={
        "user_id": "user-1",
        "system_prompt": "Be a pirate.",
    })
    assert resp.status_code == 201
    client["personality_store"].save.assert_called_once()


def test_personality_get(client):
    test_config = PersonalityConfig(
        personality_id="p-1",
        user_id="user-1",
        system_prompt="Be a pirate.",
    )
    client["personality_store"].get.return_value = test_config

    resp = client["client"].get("/api/v1/personality/p-1")
    assert resp.status_code == 200
    assert resp.json()["system_prompt"] == "Be a pirate."


def test_personality_not_found(client):
    client["personality_store"].get.return_value = None
    resp = client["client"].get("/api/v1/personality/nonexistent")
    assert resp.status_code == 404


def test_personality_delete(client):
    client["personality_store"].delete.return_value = True
    resp = client["client"].delete("/api/v1/personality/p-1")
    assert resp.status_code == 204


def test_personality_delete_not_found(client):
    client["personality_store"].delete.return_value = False
    resp = client["client"].delete("/api/v1/personality/p-1")
    assert resp.status_code == 404


def test_memory_get_history(client):
    from app.models.schemas import ChatMessage
    from app.models.enums import MessageRole

    client["memory"].get_history.return_value = [
        ChatMessage(role=MessageRole.USER, content="Hello"),
        ChatMessage(role=MessageRole.ASSISTANT, content="Hi!"),
    ]

    resp = client["client"].get("/api/v1/memory/conv-123")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_memory_not_found(client):
    client["memory"].get_history.return_value = []
    resp = client["client"].get("/api/v1/memory/nonexistent")
    assert resp.status_code == 404


def test_memory_status(client):
    client["memory"].get_status.return_value = MemoryStatusResponse(
        conversation_id="conv-123",
        turn_count=5,
        ttl_remaining_seconds=1800,
    )
    resp = client["client"].get("/api/v1/memory/conv-123/status")
    assert resp.status_code == 200
    assert resp.json()["turn_count"] == 5


def test_memory_status_not_found(client):
    client["memory"].get_status.return_value = None
    resp = client["client"].get("/api/v1/memory/nonexistent/status")
    assert resp.status_code == 404


def test_memory_delete(client):
    client["memory"].delete.return_value = True
    resp = client["client"].delete("/api/v1/memory/conv-123")
    assert resp.status_code == 204


def test_memory_delete_not_found(client):
    client["memory"].delete.return_value = False
    resp = client["client"].delete("/api/v1/memory/conv-123")
    assert resp.status_code == 404
