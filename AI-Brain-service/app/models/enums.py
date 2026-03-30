from __future__ import annotations

from enum import Enum


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class SafetyVerdict(str, Enum):
    PASS = "pass"
    FILTERED = "filtered"
    BLOCKED = "blocked"


class RetrievalSource(str, Enum):
    FAISS = "faiss"
    PINECONE = "pinecone"
