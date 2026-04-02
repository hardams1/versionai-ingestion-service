from __future__ import annotations

import logging

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class VoiceClient:
    """Interacts with the Voice Service for voice profile management."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.voice_service_url.rstrip("/")

    async def get_available_voices(self) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self._base_url}/api/v1/voices")
                if resp.status_code == 200:
                    return resp.json()
        except Exception as exc:
            logger.warning("Failed to fetch voices: %s", exc)
        return []
