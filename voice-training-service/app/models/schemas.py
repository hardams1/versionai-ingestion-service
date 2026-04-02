from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "ar": "Arabic",
    "zh": "Mandarin Chinese",
    "hi": "Hindi",
    "pt": "Portuguese",
    "bn": "Bengali",
    "ru": "Russian",
    "ja": "Japanese",
    "yo": "Yoruba",
    "pcm": "Nigerian Pidgin",
}


# --- Training Scripts ---


class ScriptSection(BaseModel):
    title: str
    instruction: str
    prompts: list[str]


class TrainingScript(BaseModel):
    language: str
    language_name: str
    sections: list[ScriptSection]
    estimated_duration_minutes: int = 5


class TrainingScriptRequest(BaseModel):
    language: str = Field(default="en", description="Language code")


# --- Voice Sample Upload ---


class VoiceSampleResponse(BaseModel):
    sample_id: str
    duration_seconds: float
    status: str
    message: str


# --- Voice Cloning ---


class CloneVoiceRequest(BaseModel):
    voice_name: Optional[str] = None


class CloneVoiceResponse(BaseModel):
    user_id: str
    elevenlabs_voice_id: Optional[str] = None
    cloning_status: str
    message: str


# --- Voice Profile ---


class VoiceProfileResponse(BaseModel):
    user_id: str
    elevenlabs_voice_id: Optional[str] = None
    voice_name: Optional[str] = None
    cloning_status: str
    primary_language: str
    preferred_languages: list[str] = []
    total_samples: int
    total_duration_seconds: float
    avg_pitch_hz: Optional[float] = None
    speaking_rate_wpm: Optional[float] = None
    voice_service_synced: bool


# --- Language ---


class DetectLanguageRequest(BaseModel):
    text: str


class DetectLanguageResponse(BaseModel):
    detected_language: str
    language_name: str
    confidence: float


class TranslateRequest(BaseModel):
    text: str
    source_language: Optional[str] = None
    target_language: str = "en"


class TranslateResponse(BaseModel):
    original_text: str
    translated_text: str
    source_language: str
    target_language: str


class UpdateLanguageRequest(BaseModel):
    primary_language: str
    preferred_languages: list[str] = []
