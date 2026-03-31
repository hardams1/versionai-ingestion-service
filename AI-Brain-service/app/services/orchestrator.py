from __future__ import annotations

import base64
import logging
import time
from typing import TYPE_CHECKING

from app.models.schemas import ChatRequest, ChatResponse
from app.models.enums import SafetyVerdict
from app.services.embedder import BaseQueryEmbedder
from app.services.integration import MediaClient
from app.services.llm import BaseLLM
from app.services.memory import ConversationMemory
from app.services.personality_store import PersonalityStore
from app.services.prompt_builder import PromptBuilder
from app.services.retriever import BaseRetriever
from app.services.safety import SafetyProcessor
from app.utils.exceptions import PersonalityError, SafetyError

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


class BrainOrchestrator:
    """
    End-to-end pipeline:
      query → embed → retrieve → build prompt → LLM → safety → respond
      optionally: → Voice (TTS) → Video Avatar (lip-sync)
    """

    def __init__(
        self,
        settings: Settings,
        retriever: BaseRetriever,
        embedder: BaseQueryEmbedder,
        llm: BaseLLM,
        memory: ConversationMemory,
        personality_store: PersonalityStore,
        prompt_builder: PromptBuilder,
        safety: SafetyProcessor,
        media_client: MediaClient | None = None,
    ) -> None:
        self._settings = settings
        self._retriever = retriever
        self._embedder = embedder
        self._llm = llm
        self._memory = memory
        self._personality_store = personality_store
        self._prompt_builder = prompt_builder
        self._safety = safety
        self._media = media_client

    async def chat(self, request: ChatRequest) -> ChatResponse:
        start = time.perf_counter()

        conversation = await self._memory.get_or_create(
            user_id=request.user_id,
            conversation_id=request.conversation_id,
        )

        personality = None
        if request.personality_id:
            personality = await self._personality_store.get(request.personality_id)
            if personality and personality.user_id != request.user_id:
                raise PersonalityError(
                    f"Personality {request.personality_id} does not belong to user {request.user_id}"
                )

        query_vector = await self._embedder.embed(request.query)

        context_chunks = await self._retriever.search(
            query_vector=query_vector,
            user_id=request.user_id,
            top_k=self._settings.retrieval_top_k,
            score_threshold=self._settings.retrieval_score_threshold,
        )

        history = await self._memory.get_history(conversation.conversation_id)

        messages = self._prompt_builder.build(
            query=request.query,
            context_chunks=context_chunks,
            conversation_history=history,
            personality=personality,
        )

        llm_response = await self._llm.generate(messages)

        safety_result = self._safety.process(
            response=llm_response.content,
            context_chunks=context_chunks,
        )

        if safety_result.verdict == SafetyVerdict.BLOCKED:
            raise SafetyError(
                f"Response blocked by safety filter: {', '.join(safety_result.flags)}"
            )

        await self._memory.add_turn(
            conversation_id=conversation.conversation_id,
            user_message=request.query,
            assistant_message=safety_result.filtered_response,
        )

        audio_b64: str | None = None
        video_b64: str | None = None

        if self._media and (request.include_audio or request.include_video):
            audio_bytes = await self._media.synthesize_audio(
                text=safety_result.filtered_response,
                user_id=request.user_id,
            )
            if audio_bytes:
                audio_b64 = base64.b64encode(audio_bytes).decode()

                if request.include_video:
                    video_bytes = await self._media.generate_video(
                        audio_bytes=audio_bytes,
                        user_id=request.user_id,
                    )
                    if video_bytes:
                        video_b64 = base64.b64encode(video_bytes).decode()

        elapsed_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "Chat completed: conv=%s, user=%s, sources=%d, safety=%s, model=%s, audio=%s, video=%s, latency=%.0fms",
            conversation.conversation_id,
            request.user_id,
            len(context_chunks),
            safety_result.verdict.value,
            llm_response.model,
            "yes" if audio_b64 else "no",
            "yes" if video_b64 else "no",
            elapsed_ms,
        )

        return ChatResponse(
            conversation_id=conversation.conversation_id,
            response=safety_result.filtered_response,
            sources=context_chunks if request.include_sources else [],
            safety_verdict=safety_result.verdict,
            model_used=llm_response.model,
            usage=llm_response.usage,
            latency_ms=round(elapsed_ms, 1),
            audio_base64=audio_b64 if request.include_audio else None,
            video_base64=video_b64 if request.include_video else None,
        )
