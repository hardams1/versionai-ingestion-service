from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import TYPE_CHECKING, AsyncIterator

from app.models.enums import MessageType, PipelineStage
from app.models.schemas import PipelineResult, WSOutgoingMessage
from app.utils.exceptions import BrainServiceError, OrchestratorError

if TYPE_CHECKING:
    from app.services.brain_client import BrainClient
    from app.services.video_client import VideoClient
    from app.services.voice_client import VoiceClient

logger = logging.getLogger(__name__)


class OrchestrationPipeline:
    """Coordinates Brain → Voice + Video Avatar in a low-latency pipeline.

    The flow is:
      1. User query → Brain Service → response text
      2. Response text → Voice Service → audio bytes  (parallel-ready)
      3. Audio bytes → Video Avatar Service → video   (depends on #2)

    Steps 2 and 3 are serialised (video needs audio), but the overall
    pipeline is streamed: each completed stage emits a WebSocket event
    so the client can render progressively.
    """

    def __init__(
        self,
        brain: BrainClient,
        voice: VoiceClient,
        video: VideoClient,
    ) -> None:
        self._brain = brain
        self._voice = voice
        self._video = video

    async def run(
        self,
        user_id: str,
        query: str,
        *,
        conversation_id: str | None = None,
        personality_id: str | None = None,
        include_audio: bool = True,
        include_video: bool = True,
        audio_format: str = "mp3",
        video_format: str = "mp4",
        request_id: str | None = None,
    ) -> PipelineResult:
        """Execute the full pipeline synchronously, returning a single result."""
        rid = request_id or str(uuid.uuid4())
        result = PipelineResult(request_id=rid)
        pipeline_start = time.perf_counter()

        try:
            brain_data = await self._brain.chat(
                user_id=user_id,
                query=query,
                conversation_id=conversation_id,
                personality_id=personality_id,
            )
            result.response_text = brain_data.get("response", "")
            result.conversation_id = brain_data.get("conversation_id", "")
            result.sources = brain_data.get("sources", [])
            result.model_used = brain_data.get("model_used", "")
            result.brain_latency_ms = brain_data.get("_brain_latency_ms", 0.0)
            result.stage = PipelineStage.BRAIN
        except BrainServiceError as exc:
            result.error = str(exc)
            result.stage = PipelineStage.ERROR
            result.total_latency_ms = (time.perf_counter() - pipeline_start) * 1000
            return result

        if include_audio and result.response_text:
            try:
                audio_b64, audio_bytes, voice_lat = await self._voice.synthesize_b64(
                    text=result.response_text,
                    user_id=user_id,
                    audio_format=audio_format,
                )
                result.audio_base64 = audio_b64
                result.voice_latency_ms = voice_lat
                result.stage = PipelineStage.VOICE

                if include_video:
                    try:
                        video_b64, video_lat = await self._video.generate_b64(
                            audio_bytes=audio_bytes,
                            user_id=user_id,
                            video_format=video_format,
                        )
                        result.video_base64 = video_b64
                        result.video_latency_ms = video_lat
                        result.stage = PipelineStage.VIDEO
                    except OrchestratorError as exc:
                        logger.warning("Video generation failed (non-fatal): %s", exc)
                        result.video_base64 = None
            except OrchestratorError as exc:
                logger.warning("Voice synthesis failed (non-fatal): %s", exc)
                result.audio_base64 = None

        result.stage = PipelineStage.COMPLETE
        result.total_latency_ms = round((time.perf_counter() - pipeline_start) * 1000, 1)
        return result

    async def run_streaming(
        self,
        user_id: str,
        query: str,
        *,
        conversation_id: str | None = None,
        personality_id: str | None = None,
        include_audio: bool = True,
        include_video: bool = True,
        audio_format: str = "mp3",
        video_format: str = "mp4",
        request_id: str | None = None,
    ) -> AsyncIterator[WSOutgoingMessage]:
        """Execute the pipeline and yield WebSocket messages as each stage completes.

        This is the primary entrypoint for WebSocket sessions — the caller
        forwards each yielded message to the client immediately.
        """
        rid = request_id or str(uuid.uuid4())
        pipeline_start = time.perf_counter()

        yield WSOutgoingMessage(
            type=MessageType.ACK,
            request_id=rid,
            data={"stage": PipelineStage.RECEIVED.value},
        )

        # --- Stage 1: Brain ---
        yield WSOutgoingMessage(
            type=MessageType.STAGE,
            request_id=rid,
            data={"stage": PipelineStage.BRAIN.value},
        )

        try:
            brain_data = await self._brain.chat(
                user_id=user_id,
                query=query,
                conversation_id=conversation_id,
                personality_id=personality_id,
            )
        except BrainServiceError as exc:
            yield WSOutgoingMessage(
                type=MessageType.ERROR,
                request_id=rid,
                data={"detail": str(exc), "stage": PipelineStage.BRAIN.value},
            )
            return

        response_text = brain_data.get("response", "")
        yield WSOutgoingMessage(
            type=MessageType.TEXT,
            request_id=rid,
            data={
                "response": response_text,
                "conversation_id": brain_data.get("conversation_id", ""),
                "sources": brain_data.get("sources", []),
                "model_used": brain_data.get("model_used", ""),
                "brain_latency_ms": brain_data.get("_brain_latency_ms", 0),
            },
        )

        audio_bytes: bytes | None = None

        # --- Stage 2: Voice (TTS) ---
        if include_audio and response_text:
            yield WSOutgoingMessage(
                type=MessageType.STAGE,
                request_id=rid,
                data={"stage": PipelineStage.VOICE.value},
            )
            try:
                audio_b64, audio_bytes, voice_lat = await self._voice.synthesize_b64(
                    text=response_text,
                    user_id=user_id,
                    audio_format=audio_format,
                )
                yield WSOutgoingMessage(
                    type=MessageType.AUDIO,
                    request_id=rid,
                    data={
                        "audio_base64": audio_b64,
                        "audio_format": audio_format,
                        "voice_latency_ms": voice_lat,
                    },
                )
            except OrchestratorError as exc:
                logger.warning("Voice synthesis failed (non-fatal): %s", exc)
                yield WSOutgoingMessage(
                    type=MessageType.ERROR,
                    request_id=rid,
                    data={"detail": f"Voice failed: {exc}", "stage": PipelineStage.VOICE.value, "fatal": False},
                )

        # --- Stage 3: Video Avatar ---
        if include_video and audio_bytes is not None:
            yield WSOutgoingMessage(
                type=MessageType.STAGE,
                request_id=rid,
                data={"stage": PipelineStage.VIDEO.value},
            )
            try:
                video_b64, video_lat = await self._video.generate_b64(
                    audio_bytes=audio_bytes,
                    user_id=user_id,
                    video_format=video_format,
                )
                yield WSOutgoingMessage(
                    type=MessageType.VIDEO,
                    request_id=rid,
                    data={
                        "video_base64": video_b64,
                        "video_format": video_format,
                        "video_latency_ms": video_lat,
                    },
                )
            except OrchestratorError as exc:
                logger.warning("Video generation failed (non-fatal): %s", exc)
                yield WSOutgoingMessage(
                    type=MessageType.ERROR,
                    request_id=rid,
                    data={"detail": f"Video failed: {exc}", "stage": PipelineStage.VIDEO.value, "fatal": False},
                )

        total_ms = round((time.perf_counter() - pipeline_start) * 1000, 1)
        yield WSOutgoingMessage(
            type=MessageType.COMPLETE,
            request_id=rid,
            data={"total_latency_ms": total_ms, "stage": PipelineStage.COMPLETE.value},
        )
