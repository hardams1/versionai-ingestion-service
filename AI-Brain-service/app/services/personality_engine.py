from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx

from app.services.embedder import BaseQueryEmbedder
from app.services.retriever import BaseRetriever

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)

IDENTITY_QUERIES = [
    "What is my name, who am I, and what is my background?",
    "What are my beliefs, values, and personality traits?",
    "How do I speak, what is my communication style and tone?",
]

CACHE_TTL = 1800  # 30 minutes


class PersonalityEngine:
    """Builds a dynamic personality profile from the user's ingested data
    AND their onboarding profile from the auth service.

    Priority: onboarding profile (structured) + vector store chunks (unstructured).
    Results are cached in Redis so subsequent requests in the same session are fast.
    """

    def __init__(
        self,
        retriever: BaseRetriever,
        embedder: BaseQueryEmbedder,
        settings: Settings,
        redis_client=None,
    ) -> None:
        self._retriever = retriever
        self._embedder = embedder
        self._settings = settings
        self._redis = redis_client
        self._local_cache: dict[str, str] = {}

    def _cache_key(self, user_id: str) -> str:
        return f"brain:identity:{user_id}"

    async def get_identity_context(self, user_id: str) -> str:
        """Return the identity context for a user, using cache when available."""
        cached = await self._get_cached(user_id)
        if cached:
            logger.debug("Identity cache hit for user=%s", user_id)
            return cached

        logger.info("Building identity context for user=%s", user_id)

        parts: list[str] = []

        onboarding = await self._fetch_onboarding_profile(user_id)
        if onboarding:
            parts.append(onboarding)

        vector_context = await self._fetch_vector_identity(user_id)
        if vector_context:
            parts.append(vector_context)

        if not parts:
            logger.info("No identity data found for user=%s", user_id)
            return ""

        identity_text = "\n\n".join(parts)

        await self._set_cached(user_id, identity_text)
        logger.info(
            "Built identity context for user=%s: %d chars (onboarding=%s, vectors=%s)",
            user_id, len(identity_text),
            "yes" if onboarding else "no",
            "yes" if vector_context else "no",
        )
        return identity_text

    async def _fetch_onboarding_profile(self, user_id: str) -> str:
        """Fetch structured onboarding data from the auth service."""
        auth_url = self._settings.auth_service_url
        if not auth_url:
            return ""

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{auth_url}/onboarding/profile/{user_id}")
                if resp.status_code != 200:
                    return ""
                data = resp.json()

            if not data.get("onboarding_completed"):
                return ""

            sections: list[str] = []

            if data.get("full_name"):
                line = f"My name is {data['full_name']}."
                if data.get("age"):
                    line += f" I'm {data['age']} years old."
                if data.get("location"):
                    line += f" I live in {data['location']}."
                sections.append(line)

            traits = data.get("personality_traits") or {}
            if traits.get("description"):
                sections.append(f"Personality: {traits['description']}")
            if traits.get("introvert_extrovert"):
                sections.append(f"I'm an {traits['introvert_extrovert']}.")
            if traits.get("core_values"):
                sections.append(f"My core values: {traits['core_values']}")

            style = data.get("communication_style") or {}
            if style.get("formality"):
                sections.append(f"I communicate in a {style['formality']} style.")
            if style.get("uses_humor"):
                sections.append("I use humor often in conversation.")
            if style.get("emotional_response_style"):
                sections.append(f"When dealing with emotions: {style['emotional_response_style']}")

            beliefs = data.get("beliefs") or {}
            for key, label in [
                ("views_money", "On money"),
                ("views_relationships", "On relationships"),
                ("views_success", "On success"),
                ("philosophical_beliefs", "Philosophy"),
            ]:
                if beliefs.get(key):
                    sections.append(f"{label}: {beliefs[key]}")

            if data.get("life_experiences"):
                sections.append(f"Life experiences:\n{data['life_experiences']}")

            tone = data.get("voice_tone") or {}
            tone_parts = []
            if tone.get("energy"):
                tone_parts.append(f"energy={tone['energy']}")
            if tone.get("response_length"):
                tone_parts.append(f"response style={tone['response_length']}")
            if tone_parts:
                sections.append(f"Voice & tone: {', '.join(tone_parts)}")

            if not sections:
                return ""

            return "--- ONBOARDING PROFILE ---\n" + "\n".join(sections) + "\n--- END ONBOARDING ---"

        except Exception:
            logger.warning("Failed to fetch onboarding profile for user=%s", user_id, exc_info=True)
            return ""

    async def _fetch_vector_identity(self, user_id: str) -> str:
        """Retrieve identity-relevant chunks from the vector store."""
        all_chunks = []
        seen_texts: set[str] = set()

        for query in IDENTITY_QUERIES:
            try:
                vector = await self._embedder.embed(query)
                chunks = await self._retriever.search(
                    query_vector=vector,
                    user_id=user_id,
                    top_k=5,
                    score_threshold=0.15,
                )
                for chunk in chunks:
                    if chunk.text not in seen_texts:
                        seen_texts.add(chunk.text)
                        all_chunks.append(chunk)
            except Exception:
                logger.warning("Identity query failed: %s", query, exc_info=True)

        if not all_chunks:
            return ""

        all_chunks.sort(key=lambda c: c.score, reverse=True)
        return "\n\n".join(c.text for c in all_chunks[:10])

    async def invalidate(self, user_id: str) -> None:
        """Clear cached identity for a user (call after new data ingestion)."""
        self._local_cache.pop(user_id, None)
        if self._redis:
            try:
                await self._redis.delete(self._cache_key(user_id))
            except Exception:
                pass

    async def _get_cached(self, user_id: str) -> str | None:
        if user_id in self._local_cache:
            return self._local_cache[user_id]
        if self._redis:
            try:
                data = await self._redis.get(self._cache_key(user_id))
                if data:
                    self._local_cache[user_id] = data
                    return data
            except Exception:
                pass
        return None

    async def _set_cached(self, user_id: str, identity_text: str) -> None:
        self._local_cache[user_id] = identity_text
        if self._redis:
            try:
                await self._redis.set(
                    self._cache_key(user_id),
                    identity_text,
                    ex=CACHE_TTL,
                )
            except Exception:
                logger.warning("Failed to cache identity in Redis for user=%s", user_id)
