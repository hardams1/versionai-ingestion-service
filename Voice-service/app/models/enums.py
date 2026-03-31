from __future__ import annotations

from enum import Enum


class TTSProvider(str, Enum):
    OPENAI = "openai"
    ELEVENLABS = "elevenlabs"
    MOCK = "mock"


class AudioFormat(str, Enum):
    MP3 = "mp3"
    OPUS = "opus"
    AAC = "aac"
    FLAC = "flac"
    WAV = "wav"
    PCM = "pcm"


class SynthesisStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
