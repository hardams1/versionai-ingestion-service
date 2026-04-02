from __future__ import annotations

import io
import logging

from pydub import AudioSegment

logger = logging.getLogger(__name__)


class AudioProcessor:
    ALLOWED_FORMATS = {
        "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
        "audio/webm", "audio/ogg", "audio/mp4", "audio/m4a",
    }

    @staticmethod
    def _normalize_content_type(ct: str) -> str:
        """Strip codec params (e.g. 'audio/webm;codecs=opus' -> 'audio/webm')."""
        return ct.split(";")[0].strip().lower()

    def validate_audio(self, data: bytes, content_type: str) -> tuple[float, str]:
        """Validate and return (duration_seconds, format_name). Raises ValueError on invalid."""
        ct = self._normalize_content_type(content_type)
        if ct not in self.ALLOWED_FORMATS and not ct.startswith("audio/"):
            raise ValueError(f"Unsupported audio format: {content_type}")

        try:
            audio = self._load_audio(data, content_type)
            duration = len(audio) / 1000.0
            if duration < 1.0:
                raise ValueError("Audio too short (minimum 1 second)")
            return duration, audio.channels
        except Exception as e:
            if "Audio too short" in str(e):
                raise
            raise ValueError(f"Could not process audio: {e}")

    def convert_to_mp3(self, data: bytes, content_type: str) -> bytes:
        """Convert any audio to MP3 for consistent storage."""
        audio = self._load_audio(data, content_type)
        buf = io.BytesIO()
        audio.export(buf, format="mp3", bitrate="128k")
        return buf.getvalue()

    def get_duration(self, data: bytes, content_type: str) -> float:
        audio = self._load_audio(data, content_type)
        return len(audio) / 1000.0

    def _load_audio(self, data: bytes, content_type: str) -> AudioSegment:
        fmt = self._guess_format(self._normalize_content_type(content_type))
        buf = io.BytesIO(data)
        if fmt:
            return AudioSegment.from_file(buf, format=fmt)
        return AudioSegment.from_file(buf)

    def _guess_format(self, ct: str) -> str | None:
        mapping = {
            "audio/mpeg": "mp3", "audio/mp3": "mp3",
            "audio/wav": "wav", "audio/x-wav": "wav",
            "audio/webm": "webm", "audio/ogg": "ogg",
            "audio/mp4": "mp4", "audio/m4a": "m4a",
        }
        return mapping.get(ct)
