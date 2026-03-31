from __future__ import annotations

import base64
import logging
import time
from typing import TYPE_CHECKING

import httpx

from app.utils.exceptions import VideoServiceError

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


class VideoClient:
    """HTTP client for the Video Avatar Service (:8004)."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.video_avatar_service_url.rstrip("/")
        self._timeout = httpx.Timeout(settings.video_timeout, connect=10.0)
        self._health_timeout = httpx.Timeout(settings.health_check_timeout, connect=3.0)
        self._default_format = settings.default_video_format

    async def generate(
        self,
        audio_bytes: bytes,
        user_id: str,
        *,
        video_format: str | None = None,
    ) -> tuple[bytes, float]:
        """Call Video Avatar /api/v1/generate/video and return (video_bytes, latency_ms)."""
        url = f"{self._base_url}/api/v1/generate/video"
        audio_b64 = base64.b64encode(audio_bytes).decode()
        payload = {
            "user_id": user_id,
            "audio_base64": audio_b64,
            "video_format": video_format or self._default_format,
        }

        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=payload)
                elapsed_ms = (time.perf_counter() - start) * 1000

                if resp.status_code != 200:
                    raise VideoServiceError(
                        f"Video Avatar returned HTTP {resp.status_code}: {resp.text[:500]}"
                    )

                video_bytes = resp.content
                logger.info(
                    "Video render OK: user=%s, %d bytes, latency=%.0fms",
                    user_id, len(video_bytes), elapsed_ms,
                )
                return video_bytes, round(elapsed_ms, 1)

        except httpx.TimeoutException as exc:
            raise VideoServiceError(f"Video Avatar timeout: {exc}") from exc
        except VideoServiceError:
            raise
        except Exception as exc:
            raise VideoServiceError(f"Video Avatar unreachable: {exc}") from exc

    async def generate_b64(
        self,
        audio_bytes: bytes,
        user_id: str,
        *,
        video_format: str | None = None,
    ) -> tuple[str, float]:
        """Generate video and return (base64_str, latency_ms)."""
        video_bytes, latency_ms = await self.generate(
            audio_bytes, user_id, video_format=video_format,
        )
        video_b64 = base64.b64encode(video_bytes).decode()
        return video_b64, latency_ms

    async def health(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=self._health_timeout) as client:
                resp = await client.get(f"{self._base_url}/health")
                if resp.status_code == 200:
                    return {"status": "healthy", "detail": resp.json().get("status")}
                return {"status": "unhealthy", "detail": f"HTTP {resp.status_code}"}
        except Exception as exc:
            return {"status": "unreachable", "detail": str(exc)}
