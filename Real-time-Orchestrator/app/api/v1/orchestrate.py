from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.dependencies import get_pipeline, verify_api_key
from app.models.schemas import OrchestrateRequest, OrchestrateResponse, StageResult
from app.services.pipeline import OrchestrationPipeline
from app.utils.exceptions import QueryTooLongError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orchestrate", tags=["orchestration"])


def _build_response(result) -> OrchestrateResponse:
    stages: dict[str, StageResult] = {}
    if result.stt_latency_ms:
        stages["stt"] = StageResult(status="ok", latency_ms=result.stt_latency_ms)
    if result.brain_latency_ms:
        stages["brain"] = StageResult(status="ok", latency_ms=result.brain_latency_ms)
    if result.voice_latency_ms:
        stages["voice"] = StageResult(status="ok", latency_ms=result.voice_latency_ms)
    if result.video_latency_ms:
        stages["video"] = StageResult(status="ok", latency_ms=result.video_latency_ms)

    return OrchestrateResponse(
        request_id=result.request_id,
        conversation_id=result.conversation_id,
        response_text=result.response_text,
        transcribed_text=result.transcribed_text,
        sources=result.sources,
        audio_base64=result.audio_base64,
        video_base64=result.video_base64,
        stages=stages,
        total_latency_ms=result.total_latency_ms,
    )


@router.post(
    "",
    response_model=OrchestrateResponse,
    summary="Run the full orchestration pipeline (HTTP fallback)",
    description=(
        "Accepts a user query, runs it through the Brain → Voice → Video Avatar "
        "pipeline, and returns the aggregated result. For real-time streaming, "
        "use the WebSocket endpoint at /ws/orchestrate instead."
    ),
)
async def orchestrate(
    request: OrchestrateRequest,
    pipeline: OrchestrationPipeline = Depends(get_pipeline),
    _auth: None = Depends(verify_api_key),
) -> OrchestrateResponse:
    request_id = str(uuid.uuid4())

    try:
        result = await pipeline.run(
            user_id=request.user_id,
            query=request.query,
            conversation_id=request.conversation_id,
            personality_id=request.personality_id,
            target_user_id=request.target_user_id,
            include_audio=request.include_audio,
            include_video=request.include_video,
            audio_format=request.audio_format,
            video_format=request.video_format,
            request_id=request_id,
            source_language=request.source_language,
            target_language=request.target_language,
        )
    except Exception as exc:
        if getattr(exc, "code", None) == "access_denied":
            raise HTTPException(status_code=403, detail=str(exc))
        raise

    if result.error:
        raise HTTPException(status_code=502, detail=result.error)

    return _build_response(result)


@router.post(
    "/audio",
    response_model=OrchestrateResponse,
    summary="Voice-input orchestration pipeline",
    description=(
        "Accepts an audio file, transcribes it via Speech-to-Text, "
        "then runs the full Brain → Voice → Video Avatar pipeline."
    ),
)
async def orchestrate_audio(
    audio: UploadFile = File(..., description="Audio file (wav, mp3, webm, ogg)"),
    user_id: str = Form(...),
    conversation_id: str | None = Form(default=None),
    personality_id: str | None = Form(default=None),
    include_audio: bool = Form(default=True),
    include_video: bool = Form(default=True),
    audio_format: str = Form(default="mp3"),
    video_format: str = Form(default="mp4"),
    target_language: str | None = Form(default=None),
    pipeline: OrchestrationPipeline = Depends(get_pipeline),
    _auth: None = Depends(verify_api_key),
) -> OrchestrateResponse:
    request_id = str(uuid.uuid4())

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    try:
        result = await pipeline.run_with_audio(
            user_id=user_id,
            audio_bytes=audio_bytes,
            conversation_id=conversation_id,
            personality_id=personality_id,
            include_audio=include_audio,
            include_video=include_video,
            audio_format=audio_format,
            video_format=video_format,
            request_id=request_id,
            target_language=target_language,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    if result.error:
        raise HTTPException(status_code=502, detail=result.error)

    return _build_response(result)
