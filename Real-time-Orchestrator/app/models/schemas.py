from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.models.enums import MessageType, PipelineStage


# ---------------------------------------------------------------------------
# WebSocket messages
# ---------------------------------------------------------------------------

class WSIncomingMessage(BaseModel):
    """Message from client over WebSocket."""
    type: MessageType
    user_id: str | None = None
    query: str | None = None
    audio_base64: str | None = Field(default=None, description="Base64-encoded audio for voice input")
    target_user_id: str | None = Field(default=None, description="Whose AI to interact with (social AI)")
    conversation_id: str | None = None
    personality_id: str | None = None
    include_audio: bool = Field(default=True)
    include_video: bool = Field(default=True)
    request_id: str | None = None
    source_language: str | None = Field(default=None, description="Override detected input language")
    target_language: str | None = Field(default=None, description="Override output language")


class WSOutgoingMessage(BaseModel):
    """Message from server over WebSocket."""
    type: MessageType
    request_id: str | None = None
    data: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# HTTP orchestrate endpoint
# ---------------------------------------------------------------------------

class OrchestrateRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1, max_length=10000)
    conversation_id: str | None = None
    personality_id: str | None = None
    target_user_id: str | None = Field(default=None, description="Whose AI to interact with (social AI)")
    include_audio: bool = Field(default=True, description="Generate TTS audio")
    include_video: bool = Field(default=True, description="Generate lip-sync video")
    audio_format: str = "mp3"
    video_format: str = "mp4"
    source_language: str | None = Field(default=None, description="Override detected input language")
    target_language: str | None = Field(default=None, description="Override output language")


class OrchestrateAudioRequest(BaseModel):
    """Response schema for the audio orchestrate endpoint."""
    user_id: str = Field(..., min_length=1)
    conversation_id: str | None = None
    personality_id: str | None = None
    include_audio: bool = Field(default=True)
    include_video: bool = Field(default=True)
    audio_format: str = "mp3"
    video_format: str = "mp4"
    target_language: str | None = None


class OrchestrateResponse(BaseModel):
    request_id: str
    conversation_id: str
    response_text: str
    transcribed_text: str | None = None
    sources: list[dict] = Field(default_factory=list)
    audio_base64: str | None = None
    video_base64: str | None = None
    stages: dict[str, StageResult] = Field(default_factory=dict)
    total_latency_ms: float


class StageResult(BaseModel):
    status: str
    latency_ms: float
    detail: str | None = None


# ---------------------------------------------------------------------------
# Health / Status
# ---------------------------------------------------------------------------

class ServiceHealth(BaseModel):
    status: str
    latency_ms: float | None = None
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    environment: str
    active_sessions: int = 0
    services: dict[str, ServiceHealth] = Field(default_factory=dict)


class ErrorDetail(BaseModel):
    detail: str
    code: str | None = None


# ---------------------------------------------------------------------------
# Internal pipeline data
# ---------------------------------------------------------------------------

class PipelineResult(BaseModel):
    """Aggregated result from the full orchestration pipeline."""
    request_id: str
    conversation_id: str = ""
    response_text: str = ""
    transcribed_text: str | None = None
    sources: list[dict] = Field(default_factory=list)
    model_used: str = ""
    audio_base64: str | None = None
    video_base64: str | None = None
    stt_latency_ms: float = 0.0
    brain_latency_ms: float = 0.0
    voice_latency_ms: float = 0.0
    video_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    error: str | None = None
    stage: PipelineStage = PipelineStage.RECEIVED
    detected_language: str | None = None
    response_language: str | None = None
