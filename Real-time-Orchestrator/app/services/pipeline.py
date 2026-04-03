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
    from app.services.settings_client import SettingsClient
    from app.services.social_client import SocialGraphClient
    from app.services.stt_client import STTClient
    from app.services.video_client import VideoClient
    from app.services.voice_client import VoiceClient
    from app.services.voice_training_client import VoiceTrainingClient

logger = logging.getLogger(__name__)


class OrchestrationPipeline:
    """Coordinates Brain → Voice + Video Avatar in a low-latency pipeline.

    The flow is:
      0. Detect language → translate input to English (if needed)
      1. English query → Brain Service → English response
      2. Translate response → user's language
      3. Translated text → Voice Service → audio bytes
      4. Audio bytes → Video Avatar Service → video
    """

    def __init__(
        self,
        brain: BrainClient,
        voice: VoiceClient,
        video: VideoClient,
        settings_client: SettingsClient | None = None,
        voice_training_client: VoiceTrainingClient | None = None,
        stt_client: STTClient | None = None,
        social_client: SocialGraphClient | None = None,
    ) -> None:
        self._brain = brain
        self._voice = voice
        self._video = video
        self._settings_client = settings_client
        self._lang_client = voice_training_client
        self._stt = stt_client
        self._social = social_client

    async def _resolve_output_flags(
        self, user_id: str, include_audio: bool, include_video: bool
    ) -> tuple[bool, bool]:
        """Apply output_mode from user settings to override flags.

        If the user has no saved settings, respects the caller's original flags.
        """
        if not self._settings_client:
            return include_audio, include_video
        try:
            prefs = await self._settings_client.get_user_output_mode(user_id)
            if prefs is None:
                return include_audio, include_video
            mode = prefs.get("output_mode", "video")
            if mode == "chat":
                return False, False
            elif mode == "voice":
                return True, False
            elif mode == "video":
                return True, True
            elif mode == "immersive":
                return True, True
        except Exception:
            pass
        return include_audio, include_video

    async def _resolve_language(
        self, user_id: str, query: str, source_lang: str | None, target_lang: str | None,
    ) -> tuple[str, str, str]:
        """Detect/resolve languages and translate query to English.

        Returns (detected_lang, user_preferred_lang, english_query).
        """
        if not self._lang_client:
            return "en", target_lang or "en", query

        detected = source_lang
        if not detected:
            detected, _ = await self._lang_client.detect_language(query)

        preferred = target_lang
        if not preferred:
            preferred = await self._lang_client.get_user_language(user_id)

        english_query = query
        if detected != "en":
            english_query = await self._lang_client.translate(query, detected, "en")
            logger.info("Translated input %s→en for user=%s", detected, user_id)

        return detected, preferred, english_query

    async def _translate_response(self, text: str, target_lang: str) -> str:
        """Translate Brain's English response to user's language."""
        if target_lang == "en" or not self._lang_client:
            return text
        translated = await self._lang_client.translate(text, "en", target_lang)
        logger.info("Translated response en→%s", target_lang)
        return translated

    async def _check_social_access(self, requester_id: str, target_user_id: str | None) -> None:
        """Check AI access and rate limits via Social Graph Service. Raises on deny."""
        if not target_user_id or not self._social:
            return
        if requester_id == target_user_id:
            return
        result = await self._social.check_access(requester_id, target_user_id)
        if not result.allowed:
            raise OrchestratorError(result.reason, code="access_denied")

    async def _transcribe_audio(self, audio_bytes: bytes, filename: str = "audio.webm") -> tuple[str, str]:
        """Transcribe audio via STT service. Returns (text, detected_language)."""
        if not self._stt:
            raise OrchestratorError("STT service not configured", code="stt_unavailable")
        result = await self._stt.transcribe(audio_bytes, filename)
        query = result.translated_text if result.translated_text else result.text
        return query, result.detected_language

    async def run(
        self,
        user_id: str,
        query: str,
        *,
        conversation_id: str | None = None,
        personality_id: str | None = None,
        target_user_id: str | None = None,
        include_audio: bool = True,
        include_video: bool = True,
        audio_format: str = "mp3",
        video_format: str = "mp4",
        request_id: str | None = None,
        source_language: str | None = None,
        target_language: str | None = None,
    ) -> PipelineResult:
        """Execute the full pipeline synchronously, returning a single result."""
        rid = request_id or str(uuid.uuid4())
        result = PipelineResult(request_id=rid)
        pipeline_start = time.perf_counter()

        await self._check_social_access(user_id, target_user_id)

        include_audio, include_video = await self._resolve_output_flags(
            user_id, include_audio, include_video,
        )

        detected_lang, target_lang, english_query = await self._resolve_language(
            user_id, query, source_language, target_language,
        )
        result.detected_language = detected_lang
        result.response_language = target_lang

        try:
            brain_data = await self._brain.chat(
                user_id=user_id,
                query=english_query,
                conversation_id=conversation_id,
                personality_id=personality_id,
            )
            english_response = brain_data.get("response", "")
            result.response_text = await self._translate_response(english_response, target_lang)
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
        target_user_id: str | None = None,
        include_audio: bool = True,
        include_video: bool = True,
        audio_format: str = "mp3",
        video_format: str = "mp4",
        request_id: str | None = None,
        source_language: str | None = None,
        target_language: str | None = None,
    ) -> AsyncIterator[WSOutgoingMessage]:
        """Execute the pipeline and yield WebSocket messages as each stage completes."""
        rid = request_id or str(uuid.uuid4())
        pipeline_start = time.perf_counter()

        await self._check_social_access(user_id, target_user_id)

        include_audio, include_video = await self._resolve_output_flags(
            user_id, include_audio, include_video,
        )

        detected_lang, target_lang, english_query = await self._resolve_language(
            user_id, query, source_language, target_language,
        )

        yield WSOutgoingMessage(
            type=MessageType.ACK,
            request_id=rid,
            data={
                "stage": PipelineStage.RECEIVED.value,
                "detected_language": detected_lang,
                "target_language": target_lang,
            },
        )

        # --- Stage 1: Brain (always processes English) ---
        yield WSOutgoingMessage(
            type=MessageType.STAGE,
            request_id=rid,
            data={"stage": PipelineStage.BRAIN.value},
        )

        try:
            brain_data = await self._brain.chat(
                user_id=user_id,
                query=english_query,
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

        english_response = brain_data.get("response", "")
        response_text = await self._translate_response(english_response, target_lang)

        yield WSOutgoingMessage(
            type=MessageType.TEXT,
            request_id=rid,
            data={
                "response": response_text,
                "conversation_id": brain_data.get("conversation_id", ""),
                "sources": brain_data.get("sources", []),
                "model_used": brain_data.get("model_used", ""),
                "brain_latency_ms": brain_data.get("_brain_latency_ms", 0),
                "detected_language": detected_lang,
                "response_language": target_lang,
            },
        )

        audio_bytes: bytes | None = None

        # --- Stage 2: Voice (TTS) — synthesizes translated text ---
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

    # ------------------------------------------------------------------
    # Audio-input variants: transcribe first, then delegate to text flow
    # ------------------------------------------------------------------

    async def run_with_audio(
        self,
        user_id: str,
        audio_bytes: bytes,
        *,
        conversation_id: str | None = None,
        personality_id: str | None = None,
        include_audio: bool = True,
        include_video: bool = True,
        audio_format: str = "mp3",
        video_format: str = "mp4",
        request_id: str | None = None,
        target_language: str | None = None,
    ) -> PipelineResult:
        """Transcribe audio then run the standard text pipeline."""
        rid = request_id or str(uuid.uuid4())
        t0 = time.perf_counter()

        query, detected_lang = await self._transcribe_audio(audio_bytes)
        stt_ms = round((time.perf_counter() - t0) * 1000, 1)
        logger.info("STT done in %.0fms: lang=%s, len=%d", stt_ms, detected_lang, len(query))

        result = await self.run(
            user_id=user_id,
            query=query,
            conversation_id=conversation_id,
            personality_id=personality_id,
            include_audio=include_audio,
            include_video=include_video,
            audio_format=audio_format,
            video_format=video_format,
            request_id=rid,
            source_language=detected_lang,
            target_language=target_language,
        )
        result.transcribed_text = query
        result.stt_latency_ms = stt_ms
        return result

    async def run_streaming_with_audio(
        self,
        user_id: str,
        audio_bytes: bytes,
        *,
        conversation_id: str | None = None,
        personality_id: str | None = None,
        include_audio: bool = True,
        include_video: bool = True,
        audio_format: str = "mp3",
        video_format: str = "mp4",
        request_id: str | None = None,
        target_language: str | None = None,
    ) -> AsyncIterator[WSOutgoingMessage]:
        """Transcribe audio then stream the standard text pipeline."""
        rid = request_id or str(uuid.uuid4())
        t0 = time.perf_counter()

        yield WSOutgoingMessage(
            type=MessageType.STAGE,
            request_id=rid,
            data={"stage": PipelineStage.TRANSCRIPTION.value},
        )

        query, detected_lang = await self._transcribe_audio(audio_bytes)
        stt_ms = round((time.perf_counter() - t0) * 1000, 1)

        yield WSOutgoingMessage(
            type=MessageType.TRANSCRIPTION,
            request_id=rid,
            data={
                "text": query,
                "detected_language": detected_lang,
                "stt_latency_ms": stt_ms,
            },
        )

        async for msg in self.run_streaming(
            user_id=user_id,
            query=query,
            conversation_id=conversation_id,
            personality_id=personality_id,
            include_audio=include_audio,
            include_video=include_video,
            audio_format=audio_format,
            video_format=video_format,
            request_id=rid,
            source_language=detected_lang,
            target_language=target_language,
        ):
            yield msg
