from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import MessageRole, SafetyVerdict


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    user_id: str = Field(..., min_length=1, description="Unique identifier for the user")
    query: str = Field(..., min_length=1, max_length=10000)
    conversation_id: str | None = Field(default=None, description="Resume an existing conversation")
    personality_id: str | None = Field(default=None, description="Override default personality")
    include_sources: bool = Field(default=True, description="Return source chunks used for grounding")


class SourceChunk(BaseModel):
    text: str
    score: float
    file_id: str | None = None
    chunk_index: int | None = None
    metadata: dict = Field(default_factory=dict)


class ChatMessage(BaseModel):
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatResponse(BaseModel):
    conversation_id: str
    response: str
    sources: list[SourceChunk] = Field(default_factory=list)
    safety_verdict: SafetyVerdict = SafetyVerdict.PASS
    model_used: str
    usage: TokenUsage | None = None
    latency_ms: float


# ---------------------------------------------------------------------------
# Personality
# ---------------------------------------------------------------------------

class PersonalityConfig(BaseModel):
    personality_id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    name: str = Field(default="Default Assistant")
    system_prompt: str = Field(..., min_length=1, max_length=5000)
    tone: str = Field(default="helpful and professional")
    constraints: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PersonalityResponse(BaseModel):
    personality_id: str
    name: str
    system_prompt: str
    tone: str
    constraints: list[str]


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------

class ConversationHistory(BaseModel):
    conversation_id: str
    user_id: str
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_active: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MemoryStatusResponse(BaseModel):
    conversation_id: str
    turn_count: int
    ttl_remaining_seconds: int | None = None


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------

class ErrorDetail(BaseModel):
    detail: str
    code: str | None = None


class DependencyHealth(BaseModel):
    status: str
    latency_ms: float | None = None
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    environment: str
    llm_provider: str
    vector_store: str
    dependencies: dict[str, DependencyHealth] = Field(default_factory=dict)
