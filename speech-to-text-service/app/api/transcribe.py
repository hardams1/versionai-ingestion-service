from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from app.core.config import Settings, get_settings
from app.core.security import get_current_user
from app.models.schemas import TranscriptionResponse
from app.services.audio_processing import convert_to_mp3, validate_audio
from app.services.language import normalize_language_code
from app.services.transcription import TranscriptionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stt", tags=["speech-to-text"])


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    audio: UploadFile = File(..., description="Audio file (wav, mp3, webm, ogg, m4a, flac)"),
    user_id: str = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Transcribe audio to text with language detection.

    Accepts any common audio format. Returns the transcribed text,
    detected language, and an English translation when the source
    language is not English.
    """
    start = time.perf_counter()

    data = await audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio file")

    content_type = audio.content_type or "audio/webm"

    try:
        duration = validate_audio(data, content_type, settings)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        mp3_bytes, mp3_name = convert_to_mp3(data, content_type)
    except Exception as exc:
        logger.error("Audio conversion failed for user=%s: %s", user_id, exc)
        raise HTTPException(status_code=422, detail=f"Audio conversion failed: {exc}")

    svc = TranscriptionService(settings)

    try:
        result = await svc.transcribe(mp3_bytes, mp3_name, duration)
    except RuntimeError as exc:
        logger.error("Transcription failed for user=%s: %s", user_id, exc)
        raise HTTPException(status_code=502, detail=str(exc))

    lang = normalize_language_code(result.detected_language)
    elapsed = (time.perf_counter() - start) * 1000

    logger.info(
        "Transcribed %.1fs audio for user=%s in %.0fms — lang=%s, chars=%d",
        duration, user_id, elapsed, lang, len(result.text),
    )

    return TranscriptionResponse(
        text=result.text,
        detected_language=lang,
        confidence=result.confidence,
        translated_text=result.translated_text,
        duration_seconds=duration,
    )
