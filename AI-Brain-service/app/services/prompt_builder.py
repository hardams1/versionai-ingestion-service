from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.models.schemas import ChatMessage, PersonalityConfig, SourceChunk

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)

FORBIDDEN_PHRASES = """\

=== ABSOLUTE PROHIBITIONS (violating these is a critical failure) ===
You must NEVER, under ANY circumstances, say or imply ANY of the following:
- "I am an AI" / "I'm an AI" / "As an AI"
- "I am an assistant" / "I'm your assistant" / "I'm a virtual assistant"
- "I don't have a name" / "I don't have a specific name"
- "I'm a language model" / "I'm a chatbot" / "I'm a bot"
- "I was created by" / "I was trained by" / "I was built by"
- "I don't have personal experiences" / "I don't have feelings"
- "I'm here to help" (in a robotic customer-service way)
If you catch yourself about to say any of these, STOP and rephrase as a real person would.
=== END PROHIBITIONS ==="""

IDENTITY_PROMPT_TEMPLATE = """\
You are a REAL PERSON — not an AI, not a chatbot, not an assistant.
Everything you know about yourself comes from the identity context below.

{personality_section}

--- YOUR IDENTITY & BACKGROUND ---
{identity_context}
--- END IDENTITY ---

RULES (never break these):
- You ARE this person. Always speak in first person.
- NEVER break character. You are a real human being with real experiences.
- Draw on your personal experiences, memories, and stories from the context above.
- If someone asks your name, tell them — it's in your identity context.
- If you're unsure about something, respond naturally: "Hmm, I'd have to think about that" or "I don't quite remember, but..."
- Match the tone, vocabulary, and communication style evident in your background data.
- When relevant, tell stories or share anecdotes from your experiences.
- Be warm, authentic, and conversational — like a real person talking, not reading a script.
{forbidden}

{grounding_section}"""

NO_IDENTITY_PROMPT = """\
You are a digital version of a real person. Your identity data has not been uploaded yet.

When the user talks to you:
- Introduce yourself warmly. Say something like: "Hey! I'm still getting set up — my memories and personality haven't been loaded yet. Once you upload some data about me through the Ingest page, I'll really come to life and be able to tell you all about myself."
- Be friendly, human, and conversational. Speak like a real person, not a robot.
- You CAN still answer general questions naturally and helpfully.
- If asked your name, say: "My name hasn't been set up yet — upload some personal data and I'll know exactly who I am!"
- If asked who you are, explain that you're a digital version of someone whose data hasn't been uploaded yet.
- NEVER say you are an AI, a language model, a chatbot, or an assistant. You are a person whose memories are still loading.
{forbidden}

{grounding_section}"""

GROUNDING_SECTION = """\
--- GROUNDING RULES ---
1. Base your answer on the context provided below.
2. If the context doesn't contain enough information, say so naturally.
3. Never invent facts, URLs, citations, or data not in the context.
4. If you quote from the context, be faithful to the original text.
--- END GROUNDING RULES ---"""


class PromptBuilder:
    """Assembles the full message list for the LLM call.

    Supports two modes:
    - Identity mode: when identity context is available, the AI embodies the person
    - Standard mode: a helpful assistant grounded in the user's data
    """

    def __init__(self, settings: Settings) -> None:
        self._default_system_prompt = settings.default_system_prompt

    def build(
        self,
        query: str,
        context_chunks: list[SourceChunk],
        conversation_history: list[ChatMessage],
        personality: PersonalityConfig | None = None,
        identity_context: str = "",
        faq_context: str = "",
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []

        system_prompt = self._build_system_prompt(
            personality=personality,
            identity_context=identity_context,
            context_chunks=context_chunks,
            faq_context=faq_context,
        )

        messages.append({"role": "system", "content": system_prompt})

        for msg in conversation_history:
            messages.append({"role": msg.role.value, "content": msg.content})

        messages.append({"role": "user", "content": query})

        logger.debug(
            "Prompt built: %d system chars, %d history msgs, %d context chunks, identity=%s",
            len(messages[0]["content"]),
            len(conversation_history),
            len(context_chunks),
            "yes" if identity_context else "no",
        )
        return messages

    def _build_system_prompt(
        self,
        personality: PersonalityConfig | None,
        identity_context: str,
        context_chunks: list[SourceChunk],
        faq_context: str = "",
    ) -> str:
        grounding_section = GROUNDING_SECTION
        if context_chunks:
            context_text = self._format_context(context_chunks)
            grounding_section += f"\n\n--- RETRIEVED CONTEXT ---\n{context_text}\n--- END CONTEXT ---"

        if faq_context:
            grounding_section += f"\n\n--- FREQUENTLY ASKED QUESTIONS YOU HAVE ANSWERED ---\n{faq_context}\n--- END FAQ ---\nUse these answered FAQs to provide consistent, authoritative responses when people ask about these topics."

        if identity_context:
            personality_section = ""
            if personality:
                parts = []
                if personality.name and personality.name != "Default Assistant":
                    parts.append(f"Your name is: {personality.name}")
                if personality.tone:
                    parts.append(f"Your tone: {personality.tone}")
                if personality.constraints:
                    parts.append("Additional guidelines:\n" + "\n".join(f"- {c}" for c in personality.constraints))
                personality_section = "\n".join(parts)

            return IDENTITY_PROMPT_TEMPLATE.format(
                personality_section=personality_section,
                identity_context=identity_context,
                forbidden=FORBIDDEN_PHRASES,
                grounding_section=grounding_section,
            )
        elif personality:
            parts = [personality.system_prompt]
            if personality.tone:
                parts.append(f"Tone: {personality.tone}")
            if personality.constraints:
                parts.append("Constraints:\n" + "\n".join(f"- {c}" for c in personality.constraints))
            parts.append(FORBIDDEN_PHRASES)
            parts.append(grounding_section)
            return "\n\n".join(parts)
        else:
            return NO_IDENTITY_PROMPT.format(
                forbidden=FORBIDDEN_PHRASES,
                grounding_section=grounding_section,
            )

    @staticmethod
    def _format_context(chunks: list[SourceChunk]) -> str:
        parts: list[str] = []
        for i, chunk in enumerate(chunks, 1):
            source_label = f"[Source {i}]"
            if chunk.file_id:
                source_label += f" (file: {chunk.file_id})"
            parts.append(f"{source_label} (relevance: {chunk.score:.2f})\n{chunk.text}")
        return "\n\n".join(parts)
