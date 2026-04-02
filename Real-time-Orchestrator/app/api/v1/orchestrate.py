from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends

from app.dependencies import get_pipeline, verify_api_key
from app.models.schemas import OrchestrateRequest, OrchestrateResponse, StageResult
from app.services.pipeline import OrchestrationPipeline
from app.utils.exceptions import QueryTooLongError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orchestrate", tags=["orchestration"])


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

    result = await pipeline.run(
        user_id=request.user_id,
        query=request.query,
        conversation_id=request.conversation_id,
        personality_id=request.personality_id,
        include_audio=request.include_audio,
        include_video=request.include_video,
        audio_format=request.audio_format,
        video_format=request.video_format,
        request_id=request_id,
        source_language=request.source_language,
        target_language=request.target_language,
    )

    if result.error:
        from fastapi import HTTPException
        raise HTTPException(status_code=502, detail=result.error)

    stages: dict[str, StageResult] = {}
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
        sources=result.sources,
        audio_base64=result.audio_base64,
        video_base64=result.video_base64,
        stages=stages,
        total_latency_ms=result.total_latency_ms,
    )
