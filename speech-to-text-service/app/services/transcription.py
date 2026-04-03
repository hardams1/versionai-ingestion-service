from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import httpx

if TYPE_CHECKING:
    from app.core.config import Settings

logger = logging.getLogger(__name__)

WHISPER_URL = "https://api.openai.com/v1/audio/transcriptions"
WHISPER_TRANSLATION_URL = "https://api.openai.com/v1/audio/translations"


@dataclass
class TranscriptionResult:
    text: str
    detected_language: str
    confidence: float
    translated_text: Optional[str]
    duration_seconds: float


class TranscriptionService:
    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.openai_api_key
        self._model = settings.whisper_model
        self._timeout = httpx.Timeout(120.0, connect=10.0)

    async def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.mp3",
        duration_seconds: float = 0.0,
    ) -> TranscriptionResult:
        """Transcribe audio using OpenAI Whisper API.

        Returns transcription in original language, detected language,
        and an English translation if the source is non-English.
        """
        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        headers = {"Authorization": f"Bearer {self._api_key}"}

        transcription_text, detected_lang = await self._call_whisper(
            audio_bytes, filename, headers, task="transcribe",
        )

        translated_text: Optional[str] = None
        if detected_lang != "en":
            translated_text, _ = await self._call_whisper(
                audio_bytes, filename, headers, task="translate",
            )

        confidence = 0.95 if len(transcription_text.strip()) > 10 else 0.7

        return TranscriptionResult(
            text=transcription_text.strip(),
            detected_language=detected_lang,
            confidence=confidence,
            translated_text=translated_text.strip() if translated_text else None,
            duration_seconds=duration_seconds,
        )

    async def _call_whisper(
        self,
        audio_bytes: bytes,
        filename: str,
        headers: dict,
        task: str = "transcribe",
    ) -> tuple:
        """Call the OpenAI Whisper endpoint.

        Returns (text, detected_language).
        """
        url = WHISPER_URL if task == "transcribe" else WHISPER_TRANSLATION_URL

        files = {"file": (filename, io.BytesIO(audio_bytes), "audio/mpeg")}
        data: dict[str, str] = {
            "model": self._model,
            "response_format": "verbose_json",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, headers=headers, files=files, data=data)

            if resp.status_code != 200:
                body = resp.text[:500]
                logger.error("Whisper API %s failed (%d): %s", task, resp.status_code, body)
                raise RuntimeError(f"Whisper API error ({resp.status_code}): {body}")

            result = resp.json()
            text = result.get("text", "")
            language = result.get("language", "en")

            logger.info(
                "Whisper %s: lang=%s, length=%d chars",
                task, language, len(text),
            )
            return text, language
