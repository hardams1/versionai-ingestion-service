from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.models.schemas import ChatMessage, PersonalityConfig, SourceChunk

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)

GROUNDING_INSTRUCTION = (
    "\n\n--- GROUNDING RULES ---\n"
    "1. Base your answer ONLY on the context provided below.\n"
    "2. If the context doesn't contain enough information, say so.\n"
    "3. Never invent facts, URLs, citations, or data not in the context.\n"
    "4. If you quote from the context, be faithful to the original text.\n"
    "5. Clearly distinguish between what the context says and your reasoning.\n"
    "--- END GROUNDING RULES ---"
)


class PromptBuilder:
    """Assembles the full message list for the LLM call."""

    def __init__(self, settings: Settings) -> None:
        self._default_system_prompt = settings.default_system_prompt

    def build(
        self,
        query: str,
        context_chunks: list[SourceChunk],
        conversation_history: list[ChatMessage],
        personality: PersonalityConfig | None = None,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []

        system_parts: list[str] = []
        if personality:
            system_parts.append(personality.system_prompt)
            if personality.tone:
                system_parts.append(f"Tone: {personality.tone}")
            if personality.constraints:
                system_parts.append("Constraints:\n" + "\n".join(f"- {c}" for c in personality.constraints))
        else:
            system_parts.append(self._default_system_prompt)

        system_parts.append(GROUNDING_INSTRUCTION)

        if context_chunks:
            context_text = self._format_context(context_chunks)
            system_parts.append(f"\n--- RETRIEVED CONTEXT ---\n{context_text}\n--- END CONTEXT ---")

        messages.append({"role": "system", "content": "\n\n".join(system_parts)})

        for msg in conversation_history:
            messages.append({"role": msg.role.value, "content": msg.content})

        messages.append({"role": "user", "content": query})

        logger.debug(
            "Prompt built: %d system chars, %d history msgs, %d context chunks",
            len(messages[0]["content"]),
            len(conversation_history),
            len(context_chunks),
        )
        return messages

    @staticmethod
    def _format_context(chunks: list[SourceChunk]) -> str:
        parts: list[str] = []
        for i, chunk in enumerate(chunks, 1):
            source_label = f"[Source {i}]"
            if chunk.file_id:
                source_label += f" (file: {chunk.file_id})"
            parts.append(f"{source_label} (relevance: {chunk.score:.2f})\n{chunk.text}")
        return "\n\n".join(parts)
