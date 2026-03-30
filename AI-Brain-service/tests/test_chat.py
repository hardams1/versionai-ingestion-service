from __future__ import annotations

import pytest

from app.models.enums import SafetyVerdict
from app.models.schemas import ChatRequest, PersonalityConfig
from app.utils.exceptions import PersonalityError


@pytest.mark.asyncio
async def test_chat_returns_response(orchestrator):
    request = ChatRequest(user_id="test-user-1", query="What is in my documents?")
    response = await orchestrator.chat(request)

    assert response.conversation_id == "test-conv-123"
    assert response.response
    assert response.safety_verdict == SafetyVerdict.PASS
    assert response.model_used == "test-model"
    assert response.latency_ms > 0


@pytest.mark.asyncio
async def test_chat_includes_sources_by_default(orchestrator):
    request = ChatRequest(user_id="test-user-1", query="Tell me about the topic.")
    response = await orchestrator.chat(request)
    assert len(response.sources) > 0
    assert response.sources[0].score > 0


@pytest.mark.asyncio
async def test_chat_excludes_sources_when_disabled(orchestrator):
    request = ChatRequest(user_id="test-user-1", query="Tell me about the topic.", include_sources=False)
    response = await orchestrator.chat(request)
    assert len(response.sources) == 0


@pytest.mark.asyncio
async def test_chat_passes_conversation_id_to_memory(orchestrator, mock_memory):
    request = ChatRequest(user_id="test-user-1", query="Follow-up question.", conversation_id="existing-conv-456")
    await orchestrator.chat(request)
    mock_memory.get_or_create.assert_called_once_with(user_id="test-user-1", conversation_id="existing-conv-456")


@pytest.mark.asyncio
async def test_chat_reports_token_usage(orchestrator):
    request = ChatRequest(user_id="test-user-1", query="Count the tokens.")
    response = await orchestrator.chat(request)
    assert response.usage is not None
    assert response.usage.total_tokens == 150


@pytest.mark.asyncio
async def test_chat_passes_user_id_to_retriever(orchestrator, mock_retriever):
    request = ChatRequest(user_id="user-abc", query="Search query")
    await orchestrator.chat(request)
    mock_retriever.search.assert_called_once()
    call_kwargs = mock_retriever.search.call_args.kwargs
    assert call_kwargs["user_id"] == "user-abc"


@pytest.mark.asyncio
async def test_chat_stores_turn_in_memory(orchestrator, mock_memory):
    request = ChatRequest(user_id="test-user-1", query="Hello!")
    await orchestrator.chat(request)
    mock_memory.add_turn.assert_called_once()
    call_kwargs = mock_memory.add_turn.call_args.kwargs
    assert call_kwargs["conversation_id"] == "test-conv-123"
    assert call_kwargs["user_message"] == "Hello!"


@pytest.mark.asyncio
async def test_chat_rejects_foreign_personality(orchestrator, mock_personality_store):
    foreign_personality = PersonalityConfig(
        personality_id="p-foreign",
        user_id="other-user",
        system_prompt="I am an evil prompt.",
    )
    mock_personality_store.get.return_value = foreign_personality

    request = ChatRequest(user_id="test-user-1", query="Hack me.", personality_id="p-foreign")
    with pytest.raises(PersonalityError, match="does not belong"):
        await orchestrator.chat(request)


@pytest.mark.asyncio
async def test_chat_accepts_own_personality(orchestrator, mock_personality_store):
    own_personality = PersonalityConfig(
        personality_id="p-mine",
        user_id="test-user-1",
        system_prompt="You are a pirate.",
    )
    mock_personality_store.get.return_value = own_personality

    request = ChatRequest(user_id="test-user-1", query="Ahoy!", personality_id="p-mine")
    response = await orchestrator.chat(request)
    assert response.response
