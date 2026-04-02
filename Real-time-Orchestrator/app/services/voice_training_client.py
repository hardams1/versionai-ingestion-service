from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


class VoiceTrainingClient:
    """HTTP client for the Voice Training Service (:8008).

    Provides language detection, translation, and voice profile queries
    used by the orchestration pipeline.
    """

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.voice_training_service_url.rstrip("/")
        self._timeout = httpx.Timeout(30.0, connect=5.0)

    async def detect_language(self, text: str) -> tuple[str, float]:
        """Return (lang_code, confidence). Falls back to ('en', 1.0)."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/language/detect",
                    json={"text": text},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data["detected_language"], data["confidence"]
        except Exception as exc:
            logger.debug("Language detection failed: %s", exc)
        return "en", 1.0

    async def translate(
        self, text: str, source_lang: str | None, target_lang: str
    ) -> str:
        """Translate text. Returns original on failure."""
        if source_lang == target_lang:
            return text
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/language/translate",
                    json={
                        "text": text,
                        "source_language": source_lang,
                        "target_language": target_lang,
                    },
                )
                if resp.status_code == 200:
                    return resp.json()["translated_text"]
        except Exception as exc:
            logger.debug("Translation failed: %s", exc)
        return text

    async def get_user_language(self, user_id: str) -> str:
        """Fetch user's primary language from their voice training profile."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    f"{self._base_url}/voice/profile/{user_id}/public",
                )
                if resp.status_code == 200:
                    return resp.json().get("primary_language", "en")
        except Exception as exc:
            logger.debug("Voice profile fetch failed for user=%s: %s", user_id, exc)
        return "en"

    async def health(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0)) as client:
                resp = await client.get(f"{self._base_url}/health")
                if resp.status_code == 200:
                    return {"status": "healthy", "detail": resp.json().get("status")}
                return {"status": "unhealthy", "detail": f"HTTP {resp.status_code}"}
        except Exception as exc:
            return {"status": "unreachable", "detail": str(exc)}
