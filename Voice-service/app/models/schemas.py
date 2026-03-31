from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.models.enums import AudioFormat, SynthesisStatus, TTSProvider


# ---------------------------------------------------------------------------
# Synthesis request / response
# ---------------------------------------------------------------------------

class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4096, description="Text to convert to speech")
    user_id: str = Field(..., min_length=1, description="User ID to resolve voice profile")
    audio_format: AudioFormat = AudioFormat.MP3
    stream: bool = Field(default=False, description="If true, returns chunked audio stream")


class SynthesizeResponse(BaseModel):
    synthesis_id: str
    user_id: str
    text_length: int
    audio_format: AudioFormat
    tts_provider: TTSProvider
    voice_id: str = Field(description="Resolved voice profile identifier")
    duration_ms: float = Field(description="Processing time in milliseconds")
    status: SynthesisStatus
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Voice profile
# ---------------------------------------------------------------------------

class VoiceProfile(BaseModel):
    user_id: str
    voice_id: str = Field(description="Provider-specific voice identifier")
    provider: TTSProvider
    display_name: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VoiceProfileResponse(BaseModel):
    user_id: str
    voice_id: str
    provider: str
    display_name: str | None = None


class VoiceProfileCreateRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    voice_id: str = Field(..., min_length=1, description="Provider-specific voice ID")
    provider: TTSProvider = TTSProvider.OPENAI
    display_name: str | None = None


# ---------------------------------------------------------------------------
# Health / Status
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    environment: str
    tts_provider: str


class ErrorDetail(BaseModel):
    detail: str
    code: str | None = None
