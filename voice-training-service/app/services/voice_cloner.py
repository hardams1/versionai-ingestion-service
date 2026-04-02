from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class VoiceCloner:
    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.elevenlabs_api_key
        self._base_url = settings.elevenlabs_api_url

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    @staticmethod
    def _deduplicate(audio_files: list[tuple[str, bytes]]) -> list[tuple[str, bytes]]:
        """Remove files with identical content (ElevenLabs rejects duplicates)."""
        seen: set[str] = set()
        unique: list[tuple[str, bytes]] = []
        for fname, data in audio_files:
            digest = hashlib.sha256(data).hexdigest()
            if digest not in seen:
                seen.add(digest)
                unique.append((fname, data))
        if len(unique) < len(audio_files):
            logger.info(
                "Deduplicated audio files: %d → %d unique",
                len(audio_files), len(unique),
            )
        return unique

    async def clone_voice(
        self,
        audio_files: list[tuple[str, bytes]],
        voice_name: str,
        description: str = "VersionAI cloned voice — high-fidelity personal voice clone",
    ) -> Optional[str]:
        """Clone voice using ElevenLabs Instant Voice Cloning.
        Returns the ElevenLabs voice_id on success, None on failure.
        """
        if not self._api_key:
            logger.error("ElevenLabs API key not configured")
            return None

        if not audio_files:
            logger.error("No audio files provided for cloning")
            return None

        audio_files = self._deduplicate(audio_files)

        files = []
        for fname, data in audio_files:
            files.append(("files", (fname, data, "audio/mpeg")))

        labels = json.dumps({
            "accent": "natural",
            "use_case": "conversational AI assistant",
            "age": "adult",
        })

        logger.info("ElevenLabs: cloning voice '%s' with %d unique samples", voice_name, len(audio_files))

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self._base_url}/voices/add",
                    headers={"xi-api-key": self._api_key},
                    data={
                        "name": voice_name,
                        "description": description,
                        "labels": labels,
                    },
                    files=files,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    voice_id = data.get("voice_id")
                    logger.info("ElevenLabs: voice cloned successfully, voice_id=%s", voice_id)
                    return voice_id
                else:
                    logger.error(
                        "ElevenLabs cloning failed (%d): %s",
                        resp.status_code, resp.text[:500],
                    )
                    return None
        except Exception as e:
            logger.error("ElevenLabs cloning error: %s", e)
            return None

    async def delete_voice(self, voice_id: str) -> bool:
        if not self._api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.delete(
                    f"{self._base_url}/voices/{voice_id}",
                    headers={"xi-api-key": self._api_key},
                )
                return resp.status_code == 200
        except Exception:
            return False
