from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from pydub import AudioSegment

if TYPE_CHECKING:
    from app.core.config import Settings

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {
    "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
    "audio/webm", "audio/ogg", "audio/mp4", "audio/m4a",
    "audio/flac", "audio/aac",
}

FORMAT_MAP = {
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "mp4",
    "audio/m4a": "m4a",
    "audio/flac": "flac",
    "audio/aac": "aac",
}


def _normalize_content_type(ct: str) -> str:
    """Strip codec params (e.g. 'audio/webm;codecs=opus' -> 'audio/webm')."""
    return ct.split(";")[0].strip().lower()


def validate_audio(data: bytes, content_type: str, settings: Settings) -> float:
    """Validate audio data and return duration in seconds.

    Raises ValueError on invalid or oversized audio.
    """
    ct = _normalize_content_type(content_type)

    if ct not in ALLOWED_CONTENT_TYPES and not ct.startswith("audio/"):
        raise ValueError(f"Unsupported audio format: {content_type}")

    if len(data) > settings.max_audio_file_size:
        max_mb = settings.max_audio_file_size / (1024 * 1024)
        raise ValueError(f"Audio file too large ({len(data) / (1024*1024):.1f} MB > {max_mb:.0f} MB limit)")

    fmt = FORMAT_MAP.get(ct, ct.split("/")[-1])
    try:
        segment = AudioSegment.from_file(io.BytesIO(data), format=fmt)
    except Exception:
        segment = AudioSegment.from_file(io.BytesIO(data))

    duration = segment.duration_seconds
    if duration > settings.max_audio_duration_seconds:
        raise ValueError(
            f"Audio too long ({duration:.1f}s > {settings.max_audio_duration_seconds:.0f}s limit)"
        )
    if duration < 0.5:
        raise ValueError("Audio too short (minimum 0.5 seconds)")

    return duration


def convert_to_mp3(data: bytes, content_type: str) -> tuple[bytes, str]:
    """Convert any audio format to MP3 bytes suitable for Whisper API.

    Returns (mp3_bytes, filename).
    """
    ct = _normalize_content_type(content_type)
    fmt = FORMAT_MAP.get(ct, ct.split("/")[-1])

    try:
        segment = AudioSegment.from_file(io.BytesIO(data), format=fmt)
    except Exception:
        segment = AudioSegment.from_file(io.BytesIO(data))

    buf = io.BytesIO()
    segment.export(buf, format="mp3", bitrate="128k")
    buf.seek(0)
    return buf.read(), "audio.mp3"
