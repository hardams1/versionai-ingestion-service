from __future__ import annotations

import asyncio
import io
import logging
import struct
import time
from abc import ABC, abstractmethod
from typing import AsyncIterator

import httpx

from app.config import Settings
from app.models.enums import AudioFormat
from app.utils.exceptions import TTSProviderError

logger = logging.getLogger(__name__)


class BaseTTSEngine(ABC):
    """Abstract TTS engine interface."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice_id: str,
        audio_format: AudioFormat = AudioFormat.MP3,
    ) -> bytes:
        """Convert text to audio bytes."""

    @abstractmethod
    async def synthesize_stream(
        self,
        text: str,
        voice_id: str,
        audio_format: AudioFormat = AudioFormat.MP3,
    ) -> AsyncIterator[bytes]:
        """Convert text to a streaming audio response."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider identifier."""


class OpenAITTSEngine(BaseTTSEngine):
    """OpenAI TTS API (tts-1 / tts-1-hd)."""

    VOICE_MAP = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}

    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key:
            raise TTSProviderError("OPENAI_API_KEY is required for OpenAI TTS")
        self._api_key = settings.openai_api_key
        self._model = settings.openai_tts_model
        self._base_url = "https://api.openai.com/v1"
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=httpx.Timeout(60.0, connect=10.0),
        )

    @property
    def provider_name(self) -> str:
        return "openai"

    def _resolve_format(self, fmt: AudioFormat) -> str:
        fmt_map = {
            AudioFormat.MP3: "mp3",
            AudioFormat.OPUS: "opus",
            AudioFormat.AAC: "aac",
            AudioFormat.FLAC: "flac",
            AudioFormat.WAV: "wav",
            AudioFormat.PCM: "pcm",
        }
        return fmt_map.get(fmt, "mp3")

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        audio_format: AudioFormat = AudioFormat.MP3,
    ) -> bytes:
        voice = voice_id if voice_id in self.VOICE_MAP else "alloy"
        payload = {
            "model": self._model,
            "input": text,
            "voice": voice,
            "response_format": self._resolve_format(audio_format),
        }
        try:
            resp = await self._client.post("/audio/speech", json=payload)
            resp.raise_for_status()
            return resp.content
        except httpx.HTTPStatusError as exc:
            raise TTSProviderError(f"OpenAI TTS returned {exc.response.status_code}: {exc.response.text}") from exc
        except httpx.RequestError as exc:
            raise TTSProviderError(f"OpenAI TTS request failed: {exc}") from exc

    async def synthesize_stream(
        self,
        text: str,
        voice_id: str,
        audio_format: AudioFormat = AudioFormat.MP3,
    ) -> AsyncIterator[bytes]:
        voice = voice_id if voice_id in self.VOICE_MAP else "alloy"
        payload = {
            "model": self._model,
            "input": text,
            "voice": voice,
            "response_format": self._resolve_format(audio_format),
        }
        try:
            async with self._client.stream("POST", "/audio/speech", json=payload) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes(chunk_size=4096):
                    yield chunk
        except httpx.HTTPStatusError as exc:
            raise TTSProviderError(f"OpenAI TTS stream error {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            raise TTSProviderError(f"OpenAI TTS stream request failed: {exc}") from exc


class ElevenLabsTTSEngine(BaseTTSEngine):
    """ElevenLabs TTS API — supports cloned voices."""

    def __init__(self, settings: Settings) -> None:
        if not settings.elevenlabs_api_key:
            raise TTSProviderError("ELEVENLABS_API_KEY is required for ElevenLabs TTS")
        self._api_key = settings.elevenlabs_api_key
        self._model_id = settings.elevenlabs_model_id
        self._default_voice_id = settings.elevenlabs_default_voice_id
        self._base_url = "https://api.elevenlabs.io/v1"
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"xi-api-key": self._api_key},
            timeout=httpx.Timeout(60.0, connect=10.0),
        )

    @property
    def provider_name(self) -> str:
        return "elevenlabs"

    def _resolve_format(self, fmt: AudioFormat) -> str:
        fmt_map = {
            AudioFormat.MP3: "mp3_44100_128",
            AudioFormat.PCM: "pcm_24000",
            AudioFormat.OPUS: "opus_48000_128",
        }
        return fmt_map.get(fmt, "mp3_44100_128")

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        audio_format: AudioFormat = AudioFormat.MP3,
    ) -> bytes:
        vid = voice_id or self._default_voice_id
        if not vid:
            raise TTSProviderError("No voice_id provided and no default ElevenLabs voice configured")
        payload = {
            "text": text,
            "model_id": self._model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 1.0,
                "style": 0.4,
                "use_speaker_boost": True,
            },
        }
        try:
            resp = await self._client.post(
                f"/text-to-speech/{vid}",
                json=payload,
                headers={"Accept": f"audio/{self._resolve_format(audio_format).split('_')[0]}"},
                params={"output_format": self._resolve_format(audio_format)},
            )
            resp.raise_for_status()
            return resp.content
        except httpx.HTTPStatusError as exc:
            raise TTSProviderError(f"ElevenLabs returned {exc.response.status_code}: {exc.response.text}") from exc
        except httpx.RequestError as exc:
            raise TTSProviderError(f"ElevenLabs request failed: {exc}") from exc

    async def synthesize_stream(
        self,
        text: str,
        voice_id: str,
        audio_format: AudioFormat = AudioFormat.MP3,
    ) -> AsyncIterator[bytes]:
        vid = voice_id or self._default_voice_id
        if not vid:
            raise TTSProviderError("No voice_id provided and no default ElevenLabs voice configured")
        payload = {
            "text": text,
            "model_id": self._model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 1.0,
                "style": 0.4,
                "use_speaker_boost": True,
            },
        }
        try:
            async with self._client.stream(
                "POST",
                f"/text-to-speech/{vid}/stream",
                json=payload,
                params={"output_format": self._resolve_format(audio_format)},
            ) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes(chunk_size=4096):
                    yield chunk
        except httpx.HTTPStatusError as exc:
            raise TTSProviderError(f"ElevenLabs stream error {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            raise TTSProviderError(f"ElevenLabs stream failed: {exc}") from exc


class MockTTSEngine(BaseTTSEngine):
    """Development/testing TTS that generates a silent WAV file."""

    @property
    def provider_name(self) -> str:
        return "mock"

    def _generate_silent_wav(self, duration_seconds: float = 1.0, sample_rate: int = 24000) -> bytes:
        num_samples = int(sample_rate * duration_seconds)
        data_size = num_samples * 2  # 16-bit mono
        buf = io.BytesIO()
        buf.write(b"RIFF")
        buf.write(struct.pack("<I", 36 + data_size))
        buf.write(b"WAVE")
        buf.write(b"fmt ")
        buf.write(struct.pack("<I", 16))
        buf.write(struct.pack("<HHIIHH", 1, 1, sample_rate, sample_rate * 2, 2, 16))
        buf.write(b"data")
        buf.write(struct.pack("<I", data_size))
        buf.write(b"\x00" * data_size)
        return buf.getvalue()

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        audio_format: AudioFormat = AudioFormat.MP3,
    ) -> bytes:
        duration = max(0.5, len(text) / 150.0)
        logger.info("MockTTS: generating %.1fs silent audio for voice=%s (%d chars)", duration, voice_id, len(text))
        await asyncio.sleep(0.1)
        return self._generate_silent_wav(duration)

    async def synthesize_stream(
        self,
        text: str,
        voice_id: str,
        audio_format: AudioFormat = AudioFormat.MP3,
    ) -> AsyncIterator[bytes]:
        audio = await self.synthesize(text, voice_id, audio_format)
        chunk_size = 4096
        for i in range(0, len(audio), chunk_size):
            yield audio[i : i + chunk_size]
            await asyncio.sleep(0.01)


def create_tts_engine(settings: Settings) -> BaseTTSEngine:
    """Factory — instantiate the configured TTS provider."""
    provider = settings.tts_provider
    if provider == "openai":
        return OpenAITTSEngine(settings)
    elif provider == "elevenlabs":
        return ElevenLabsTTSEngine(settings)
    elif provider == "mock":
        return MockTTSEngine()
    else:
        raise TTSProviderError(f"Unknown TTS provider: {provider}")
