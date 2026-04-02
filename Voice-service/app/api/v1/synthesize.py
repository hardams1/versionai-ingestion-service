from __future__ import annotations

import logging
import time
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.config import Settings, get_settings
from app.dependencies import get_tts_engine, get_tts_registry, get_voice_profile_service, verify_api_key
from app.models.enums import AudioFormat, SynthesisStatus, TTSProvider
from app.models.schemas import SynthesizeRequest, SynthesizeResponse
from app.services.tts import BaseTTSEngine
from app.services.voice_profile import VoiceProfileService
from app.utils.exceptions import TextTooLongError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/synthesize", tags=["synthesis"])

AUDIO_CONTENT_TYPES = {
    AudioFormat.MP3: "audio/mpeg",
    AudioFormat.OPUS: "audio/opus",
    AudioFormat.AAC: "audio/aac",
    AudioFormat.FLAC: "audio/flac",
    AudioFormat.WAV: "audio/wav",
    AudioFormat.PCM: "audio/pcm",
}


@router.post(
    "",
    response_model=SynthesizeResponse,
    summary="Validate and preview synthesis parameters",
    description=(
        "Resolves the user's voice profile and validates the request "
        "without calling the TTS engine.  Use /synthesize/audio to "
        "generate actual audio."
    ),
)
async def synthesize_preview(
    request: SynthesizeRequest,
    settings: Settings = Depends(get_settings),
    tts: BaseTTSEngine = Depends(get_tts_engine),
    profile_svc: VoiceProfileService = Depends(get_voice_profile_service),
    _auth: None = Depends(verify_api_key),
) -> SynthesizeResponse:
    if len(request.text) > settings.max_text_length:
        raise TextTooLongError(len(request.text), settings.max_text_length)

    profile = await profile_svc.resolve_voice(request.user_id)

    return SynthesizeResponse(
        synthesis_id=str(uuid.uuid4()),
        user_id=request.user_id,
        text_length=len(request.text),
        audio_format=request.audio_format,
        tts_provider=TTSProvider(tts.provider_name),
        voice_id=profile.voice_id,
        duration_ms=0.0,
        status=SynthesisStatus.PENDING,
    )


@router.post(
    "/audio",
    summary="Synthesize and return audio based on user's voice profile",
    description=(
        "Resolves the user's cloned voice profile, synthesizes speech "
        "via the configured TTS engine, and returns the audio bytes.  "
        "Set stream=true for chunked transfer."
    ),
)
async def synthesize_audio(
    request: SynthesizeRequest,
    settings: Settings = Depends(get_settings),
    profile_svc: VoiceProfileService = Depends(get_voice_profile_service),
    _auth: None = Depends(verify_api_key),
) -> StreamingResponse:
    if len(request.text) > settings.max_text_length:
        raise TextTooLongError(len(request.text), settings.max_text_length)

    profile = await profile_svc.resolve_voice(request.user_id)

    registry = get_tts_registry()
    tts = registry.get(profile.provider.value)

    content_type = AUDIO_CONTENT_TYPES.get(request.audio_format, "audio/mpeg")

    logger.info(
        "Synthesizing audio for user=%s voice=%s provider=%s engine=%s (%d chars, stream=%s)",
        request.user_id, profile.voice_id, profile.provider.value,
        tts.provider_name, len(request.text), request.stream,
    )

    if request.stream:
        return StreamingResponse(
            tts.synthesize_stream(request.text, profile.voice_id, request.audio_format),
            media_type=content_type,
            headers={"X-Voice-ID": profile.voice_id, "X-User-ID": request.user_id},
        )

    start = time.perf_counter()
    audio_data = await tts.synthesize(request.text, profile.voice_id, request.audio_format)
    elapsed_ms = (time.perf_counter() - start) * 1000

    logger.info(
        "Synthesized %d bytes for user=%s voice=%s via %s in %.1fms",
        len(audio_data), request.user_id, profile.voice_id, tts.provider_name, elapsed_ms,
    )

    async def _yield_bytes():
        yield audio_data

    return StreamingResponse(
        _yield_bytes(),
        media_type=content_type,
        headers={
            "Content-Length": str(len(audio_data)),
            "X-Voice-ID": profile.voice_id,
            "X-User-ID": request.user_id,
        },
    )
