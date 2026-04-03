from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class TranscriptionResponse(BaseModel):
    text: str = Field(..., description="Transcribed text in the original language")
    detected_language: str = Field(..., description="ISO 639-1 language code")
    confidence: float = Field(..., ge=0.0, le=1.0)
    translated_text: Optional[str] = Field(
        default=None,
        description="English translation (populated when source language is not English)",
    )
    duration_seconds: float = Field(..., ge=0.0)


class ErrorResponse(BaseModel):
    detail: str
