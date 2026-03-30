from __future__ import annotations

import pytest

from app.models.schemas import PersonalityConfig
from app.services.personality_store import PersonalityStore


@pytest.fixture
def store(settings):
    """PersonalityStore without Redis — tests in-memory fallback."""
    s = PersonalityStore(settings)
    return s


@pytest.mark.asyncio
async def test_save_and_get(store):
    await store.initialize()
    config = PersonalityConfig(
        personality_id="p-1",
        user_id="user-1",
        system_prompt="Be a pirate.",
    )
    saved = await store.save(config)
    assert saved.personality_id == "p-1"

    loaded = await store.get("p-1")
    assert loaded is not None
    assert loaded.system_prompt == "Be a pirate."


@pytest.mark.asyncio
async def test_get_missing_returns_none(store):
    await store.initialize()
    result = await store.get("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_list_for_user(store):
    await store.initialize()
    await store.save(PersonalityConfig(personality_id="p-1", user_id="user-1", system_prompt="Prompt 1"))
    await store.save(PersonalityConfig(personality_id="p-2", user_id="user-1", system_prompt="Prompt 2"))
    await store.save(PersonalityConfig(personality_id="p-3", user_id="user-2", system_prompt="Prompt 3"))

    user1_personalities = await store.list_for_user("user-1")
    assert len(user1_personalities) == 2
    ids = {p.personality_id for p in user1_personalities}
    assert ids == {"p-1", "p-2"}


@pytest.mark.asyncio
async def test_delete(store):
    await store.initialize()
    await store.save(PersonalityConfig(personality_id="p-1", user_id="user-1", system_prompt="Prompt"))

    deleted = await store.delete("p-1")
    assert deleted is True

    result = await store.get("p-1")
    assert result is None


@pytest.mark.asyncio
async def test_delete_nonexistent(store):
    await store.initialize()
    deleted = await store.delete("nonexistent")
    assert deleted is False
