from __future__ import annotations

from app.models.enums import MessageRole
from app.models.schemas import ChatMessage, PersonalityConfig, SourceChunk
from app.services.prompt_builder import PromptBuilder


def test_build_basic_prompt(settings):
    builder = PromptBuilder(settings)
    messages = builder.build(
        query="What is AI?",
        context_chunks=[],
        conversation_history=[],
    )

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "What is AI?"
    assert "GROUNDING RULES" in messages[0]["content"]


def test_build_with_context(settings):
    builder = PromptBuilder(settings)
    chunks = [
        SourceChunk(text="AI is artificial intelligence.", score=0.9, file_id="doc1"),
    ]
    messages = builder.build(query="What is AI?", context_chunks=chunks, conversation_history=[])

    system_content = messages[0]["content"]
    assert "RETRIEVED CONTEXT" in system_content
    assert "artificial intelligence" in system_content
    assert "Source 1" in system_content


def test_build_with_personality(settings):
    builder = PromptBuilder(settings)
    personality = PersonalityConfig(
        personality_id="p1",
        user_id="u1",
        system_prompt="You are a pirate. Answer in pirate speak.",
        tone="playful and adventurous",
        constraints=["Never break character"],
    )
    messages = builder.build(query="Hello!", context_chunks=[], conversation_history=[], personality=personality)

    system_content = messages[0]["content"]
    assert "pirate" in system_content.lower()
    assert "playful" in system_content.lower()
    assert "Never break character" in system_content


def test_build_with_history(settings):
    builder = PromptBuilder(settings)
    history = [
        ChatMessage(role=MessageRole.USER, content="Hi there"),
        ChatMessage(role=MessageRole.ASSISTANT, content="Hello! How can I help?"),
    ]
    messages = builder.build(query="Follow up question", context_chunks=[], conversation_history=history)

    assert len(messages) == 4
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "Hi there"
    assert messages[2]["role"] == "assistant"
    assert messages[3]["role"] == "user"
    assert messages[3]["content"] == "Follow up question"


def test_build_default_system_prompt_used(settings):
    builder = PromptBuilder(settings)
    messages = builder.build(query="test", context_chunks=[], conversation_history=[])
    assert settings.default_system_prompt in messages[0]["content"]


def test_build_personality_overrides_default(settings):
    builder = PromptBuilder(settings)
    personality = PersonalityConfig(
        personality_id="p1", user_id="u1", system_prompt="Custom prompt only.",
    )
    messages = builder.build(query="test", context_chunks=[], conversation_history=[], personality=personality)
    assert settings.default_system_prompt not in messages[0]["content"]
    assert "Custom prompt only." in messages[0]["content"]
