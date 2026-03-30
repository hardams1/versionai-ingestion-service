from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from app.models.schemas import (
    ChatRequest,
    ConversationHistory,
    PersonalityConfig,
    SourceChunk,
    TokenUsage,
)
from app.models.enums import MessageRole, SafetyVerdict
from app.services.llm import LLMResponse
from app.services.memory import ConversationMemory
from app.services.orchestrator import BrainOrchestrator
from app.services.personality_store import PersonalityStore
from app.services.prompt_builder import PromptBuilder
from app.services.safety import SafetyProcessor
from app.utils.exceptions import SafetyError


@pytest.mark.asyncio
async def test_full_pipeline_with_memory_fallback(settings):
    """End-to-end: orchestrator with in-memory memory + real prompt builder + real safety."""
    memory = ConversationMemory(settings)
    # Don't call initialize() — no Redis, pure fallback

    personality_store = PersonalityStore(settings)
    await personality_store.initialize()

    mock_retriever = AsyncMock()
    mock_retriever.search.return_value = [
        SourceChunk(text="The capital of France is Paris.", score=0.95, file_id="geo-1", chunk_index=0),
    ]

    mock_embedder = AsyncMock()
    mock_embedder.embed.return_value = [0.1] * 1536

    mock_llm = AsyncMock()
    mock_llm.generate.return_value = LLMResponse(
        content="Based on the provided context, the capital of France is Paris.",
        model="test-model",
        usage=TokenUsage(prompt_tokens=200, completion_tokens=30, total_tokens=230),
        finish_reason="stop",
    )

    orchestrator = BrainOrchestrator(
        settings=settings,
        retriever=mock_retriever,
        embedder=mock_embedder,
        llm=mock_llm,
        memory=memory,
        personality_store=personality_store,
        prompt_builder=PromptBuilder(settings),
        safety=SafetyProcessor(settings),
    )

    # First turn
    resp1 = await orchestrator.chat(ChatRequest(user_id="user-1", query="What is the capital of France?"))
    assert "Paris" in resp1.response
    assert resp1.sources[0].score == 0.95
    conv_id = resp1.conversation_id

    # Second turn — same conversation
    mock_llm.generate.return_value = LLMResponse(
        content="It has a population of about 2.1 million people.",
        model="test-model",
        usage=TokenUsage(prompt_tokens=300, completion_tokens=25, total_tokens=325),
    )
    resp2 = await orchestrator.chat(ChatRequest(
        user_id="user-1", query="What is its population?", conversation_id=conv_id,
    ))
    assert resp2.conversation_id == conv_id

    # Verify history was passed to prompt builder (LLM received history)
    last_call_messages = mock_llm.generate.call_args[0][0]
    user_messages = [m for m in last_call_messages if m["role"] == "user"]
    assert len(user_messages) >= 2


@pytest.mark.asyncio
async def test_pipeline_blocks_pii_in_response(settings):
    """Safety processor blocks responses containing PII."""
    memory = ConversationMemory(settings)

    mock_llm = AsyncMock()
    mock_llm.generate.return_value = LLMResponse(
        content="Your SSN is 123-45-6789.",
        model="test-model",
        usage=TokenUsage(prompt_tokens=50, completion_tokens=10, total_tokens=60),
    )

    orchestrator = BrainOrchestrator(
        settings=settings,
        retriever=AsyncMock(search=AsyncMock(return_value=[])),
        embedder=AsyncMock(embed=AsyncMock(return_value=[0.1] * 1536)),
        llm=mock_llm,
        memory=memory,
        personality_store=AsyncMock(get=AsyncMock(return_value=None)),
        prompt_builder=PromptBuilder(settings),
        safety=SafetyProcessor(settings),
    )

    with pytest.raises(SafetyError, match="blocked"):
        await orchestrator.chat(ChatRequest(user_id="user-1", query="Show my SSN"))


@pytest.mark.asyncio
async def test_pipeline_with_personality(settings):
    """Personality config modifies the system prompt sent to the LLM."""
    memory = ConversationMemory(settings)

    personality_store = PersonalityStore(settings)
    await personality_store.initialize()
    await personality_store.save(PersonalityConfig(
        personality_id="pirate",
        user_id="user-1",
        system_prompt="You are a pirate captain. Respond in pirate speak.",
        tone="adventurous",
        constraints=["Always say 'Arrr!'"],
    ))

    captured_messages = []

    async def capture_generate(messages, **kwargs):
        captured_messages.extend(messages)
        return LLMResponse(
            content="Arrr! The answer be Paris, matey!",
            model="test-model",
            usage=TokenUsage(prompt_tokens=100, completion_tokens=20, total_tokens=120),
        )

    mock_llm = AsyncMock()
    mock_llm.generate = capture_generate

    orchestrator = BrainOrchestrator(
        settings=settings,
        retriever=AsyncMock(search=AsyncMock(return_value=[])),
        embedder=AsyncMock(embed=AsyncMock(return_value=[0.1] * 1536)),
        llm=mock_llm,
        memory=memory,
        personality_store=personality_store,
        prompt_builder=PromptBuilder(settings),
        safety=SafetyProcessor(settings),
    )

    resp = await orchestrator.chat(ChatRequest(
        user_id="user-1", query="Where is France?", personality_id="pirate",
    ))
    assert "Arrr" in resp.response

    system_msg = captured_messages[0]
    assert "pirate" in system_msg["content"].lower()
    assert "Arrr" in system_msg["content"]
