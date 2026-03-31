from __future__ import annotations

import base64
import logging
import time
from typing import TYPE_CHECKING

import httpx

from app.utils.exceptions import VoiceServiceError

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


class VoiceClient:
    """HTTP client for the Voice Service (:8003)."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.voice_service_url.rstrip("/")
        self._timeout = httpx.Timeout(settings.voice_timeout, connect=10.0)
        self._health_timeout = httpx.Timeout(settings.health_check_timeout, connect=3.0)
        self._default_format = settings.default_audio_format

    async def synthesize(
        self,
        text: str,
        user_id: str,
        *,
        audio_format: str | None = None,
    ) -> tuple[bytes, float]:
        """Call Voice /api/v1/synthesize/audio and return (audio_bytes, latency_ms)."""
        url = f"{self._base_url}/api/v1/synthesize/audio"
        payload = {
            "text": text,
            "user_id": user_id,
            "audio_format": audio_format or self._default_format,
        }

        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=payload)
                elapsed_ms = (time.perf_counter() - start) * 1000

                if resp.status_code != 200:
                    raise VoiceServiceError(
                        f"Voice returned HTTP {resp.status_code}: {resp.text[:500]}"
                    )

                audio_bytes = resp.content
                logger.info(
                    "Voice synthesis OK: user=%s, %d bytes, latency=%.0fms",
                    user_id, len(audio_bytes), elapsed_ms,
                )
                return audio_bytes, round(elapsed_ms, 1)

        except httpx.TimeoutException as exc:
            raise VoiceServiceError(f"Voice service timeout: {exc}") from exc
        except VoiceServiceError:
            raise
        except Exception as exc:
            raise VoiceServiceError(f"Voice service unreachable: {exc}") from exc

    async def synthesize_b64(
        self,
        text: str,
        user_id: str,
        *,
        audio_format: str | None = None,
    ) -> tuple[str, bytes, float]:
        """Synthesize and return (base64_str, raw_bytes, latency_ms).

        The raw bytes are needed downstream for the Video Avatar pipeline.
        """
        audio_bytes, latency_ms = await self.synthesize(
            text, user_id, audio_format=audio_format,
        )
        audio_b64 = base64.b64encode(audio_bytes).decode()
        return audio_b64, audio_bytes, latency_ms

    async def health(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=self._health_timeout) as client:
                resp = await client.get(f"{self._base_url}/health")
                if resp.status_code == 200:
                    return {"status": "healthy", "detail": resp.json().get("status")}
                return {"status": "unhealthy", "detail": f"HTTP {resp.status_code}"}
        except Exception as exc:
            return {"status": "unreachable", "detail": str(exc)}
