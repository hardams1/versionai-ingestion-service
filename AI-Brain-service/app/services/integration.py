from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(5.0, connect=3.0)
_MEDIA_TIMEOUT = httpx.Timeout(120.0, connect=10.0)


class SiblingServiceClient:
    """
    Lightweight async client for health-checking sibling microservices.
    Used by the /health endpoint to report full system status.
    """

    def __init__(self, settings: Settings) -> None:
        self._ingestion_url = settings.ingestion_service_url
        self._processing_url = settings.processing_service_url
        self._voice_url = settings.voice_service_url
        self._video_avatar_url = settings.video_avatar_service_url

    async def check_ingestion(self) -> dict:
        return await self._check("ingestion", self._ingestion_url)

    async def check_processing(self) -> dict:
        return await self._check("processing", self._processing_url)

    async def check_voice(self) -> dict:
        return await self._check("voice", self._voice_url)

    async def check_video_avatar(self) -> dict:
        return await self._check("video_avatar", self._video_avatar_url)

    @staticmethod
    async def _check(name: str, base_url: str | None) -> dict:
        if not base_url:
            return {"status": "not_configured"}

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(f"{base_url.rstrip('/')}/health")
                if resp.status_code == 200:
                    return {"status": "healthy", "detail": resp.json()}
                return {"status": "unhealthy", "detail": f"HTTP {resp.status_code}"}
        except httpx.TimeoutException:
            return {"status": "timeout"}
        except Exception as exc:
            return {"status": "unreachable", "detail": str(exc)}


class MediaClient:
    """Calls Voice and Video Avatar services to generate audio/video from text.

    Flow: text → Voice (TTS) → audio bytes → Video Avatar → video bytes
    """

    def __init__(self, settings: Settings) -> None:
        self._voice_url = settings.voice_service_url
        self._video_avatar_url = settings.video_avatar_service_url

    @property
    def voice_available(self) -> bool:
        return bool(self._voice_url)

    @property
    def video_avatar_available(self) -> bool:
        return bool(self._video_avatar_url)

    async def synthesize_audio(self, text: str, user_id: str) -> bytes | None:
        if not self._voice_url:
            return None

        url = f"{self._voice_url.rstrip('/')}/api/v1/synthesize/audio"
        try:
            async with httpx.AsyncClient(timeout=_MEDIA_TIMEOUT) as client:
                resp = await client.post(url, json={
                    "text": text,
                    "user_id": user_id,
                    "audio_format": "mp3",
                })
                if resp.status_code == 200:
                    logger.info(
                        "Voice synthesis OK for user=%s (%d bytes)",
                        user_id, len(resp.content),
                    )
                    return resp.content
                logger.warning("Voice synthesis failed: HTTP %d", resp.status_code)
                return None
        except Exception as exc:
            logger.warning("Voice synthesis error: %s", exc)
            return None

    async def generate_video(self, audio_bytes: bytes, user_id: str) -> bytes | None:
        if not self._video_avatar_url:
            return None

        url = f"{self._video_avatar_url.rstrip('/')}/api/v1/generate/video"
        audio_b64 = base64.b64encode(audio_bytes).decode()
        try:
            async with httpx.AsyncClient(timeout=_MEDIA_TIMEOUT) as client:
                resp = await client.post(url, json={
                    "user_id": user_id,
                    "audio_base64": audio_b64,
                    "video_format": "mp4",
                })
                if resp.status_code == 200:
                    logger.info(
                        "Video avatar OK for user=%s (%d bytes)",
                        user_id, len(resp.content),
                    )
                    return resp.content
                logger.warning("Video avatar failed: HTTP %d", resp.status_code)
                return None
        except Exception as exc:
            logger.warning("Video avatar error: %s", exc)
            return None
