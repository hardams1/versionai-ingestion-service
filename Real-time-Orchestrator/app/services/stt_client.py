from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class STTResult:
    text: str
    detected_language: str
    confidence: float
    translated_text: str | None
    duration_seconds: float


class STTClient:
    """HTTP client for the Speech-to-Text Service (:8009)."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.stt_service_url.rstrip("/")
        self._timeout = httpx.Timeout(120.0, connect=10.0)

    async def transcribe(self, audio_bytes: bytes, filename: str = "audio.webm", content_type: str = "audio/webm") -> STTResult:
        """Send audio to the STT service and return transcription."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                files = {"audio": (filename, audio_bytes, content_type)}
                resp = await client.post(
                    f"{self._base_url}/stt/transcribe",
                    files=files,
                )

                if resp.status_code != 200:
                    body = resp.text[:500]
                    logger.error("STT service error (%d): %s", resp.status_code, body)
                    raise RuntimeError(f"STT service error ({resp.status_code}): {body}")

                data = resp.json()
                return STTResult(
                    text=data["text"],
                    detected_language=data["detected_language"],
                    confidence=data["confidence"],
                    translated_text=data.get("translated_text"),
                    duration_seconds=data.get("duration_seconds", 0.0),
                )
        except httpx.HTTPError as exc:
            logger.error("STT service unreachable: %s", exc)
            raise RuntimeError(f"STT service unreachable: {exc}") from exc

    async def health(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0)) as client:
                resp = await client.get(f"{self._base_url}/health")
                if resp.status_code == 200:
                    return {"status": "healthy", "detail": resp.json().get("status")}
                return {"status": "unhealthy", "detail": f"HTTP {resp.status_code}"}
        except Exception as exc:
            return {"status": "unreachable", "detail": str(exc)}
