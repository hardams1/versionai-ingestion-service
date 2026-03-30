from __future__ import annotations

import pytest

from app.models.enums import MessageRole
from app.services.memory import ConversationMemory


@pytest.fixture
def memory(settings):
    """Memory service without Redis — tests fallback path."""
    mem = ConversationMemory(settings)
    return mem


@pytest.mark.asyncio
async def test_get_or_create_new_conversation(memory):
    history = await memory.get_or_create(user_id="user-1")
    assert history.conversation_id
    assert history.user_id == "user-1"
    assert history.messages == []


@pytest.mark.asyncio
async def test_get_or_create_preserves_conversation_id(memory):
    h1 = await memory.get_or_create(user_id="user-1")
    h2 = await memory.get_or_create(user_id="user-1", conversation_id=h1.conversation_id)
    assert h2.conversation_id == h1.conversation_id


@pytest.mark.asyncio
async def test_add_turn_persists_messages(memory):
    h1 = await memory.get_or_create(user_id="user-1")
    await memory.add_turn(h1.conversation_id, "Hello!", "Hi there!")

    messages = await memory.get_history(h1.conversation_id)
    assert len(messages) == 2
    assert messages[0].role == MessageRole.USER
    assert messages[0].content == "Hello!"
    assert messages[1].role == MessageRole.ASSISTANT
    assert messages[1].content == "Hi there!"


@pytest.mark.asyncio
async def test_add_turn_trims_to_max_turns(settings):
    settings.memory_max_turns = 2
    memory = ConversationMemory(settings)

    h = await memory.get_or_create(user_id="user-1")
    for i in range(5):
        await memory.add_turn(h.conversation_id, f"Q{i}", f"A{i}")

    messages = await memory.get_history(h.conversation_id)
    assert len(messages) == 4  # 2 turns * 2 messages/turn
    assert messages[0].content == "Q3"


@pytest.mark.asyncio
async def test_add_turn_missing_conversation_creates_ephemeral(memory):
    result = await memory.add_turn("nonexistent-id", "Q", "A")
    assert result.conversation_id == "nonexistent-id"
    assert len(result.messages) == 2


@pytest.mark.asyncio
async def test_delete_conversation(memory):
    h = await memory.get_or_create(user_id="user-1")
    await memory.add_turn(h.conversation_id, "Q", "A")

    deleted = await memory.delete(h.conversation_id)
    assert deleted is True

    messages = await memory.get_history(h.conversation_id)
    assert messages == []


@pytest.mark.asyncio
async def test_delete_nonexistent_returns_false(memory):
    deleted = await memory.delete("nonexistent")
    assert deleted is False


@pytest.mark.asyncio
async def test_get_status_returns_none_for_missing(memory):
    status = await memory.get_status("nonexistent")
    assert status is None


@pytest.mark.asyncio
async def test_get_status_returns_turn_count(memory):
    h = await memory.get_or_create(user_id="user-1")
    await memory.add_turn(h.conversation_id, "Q1", "A1")
    await memory.add_turn(h.conversation_id, "Q2", "A2")

    status = await memory.get_status(h.conversation_id)
    assert status is not None
    assert status.turn_count == 2


@pytest.mark.asyncio
async def test_health_check_without_redis(memory):
    ok = await memory.health_check()
    assert ok is False
