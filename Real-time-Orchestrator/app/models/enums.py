from __future__ import annotations

from enum import Enum


class SessionState(str, Enum):
    CONNECTED = "connected"
    PROCESSING = "processing"
    IDLE = "idle"
    DISCONNECTED = "disconnected"


class PipelineStage(str, Enum):
    RECEIVED = "received"
    TRANSCRIPTION = "transcription"
    BRAIN = "brain"
    VOICE = "voice"
    VIDEO = "video"
    COMPLETE = "complete"
    ERROR = "error"


class MessageType(str, Enum):
    """WebSocket message types (client → server and server → client)."""

    # Client → Server
    QUERY = "query"
    AUDIO_QUERY = "audio_query"
    PING = "ping"

    # Server → Client
    ACK = "ack"
    TRANSCRIPTION = "transcription"
    TEXT = "text"
    AUDIO = "audio"
    VIDEO = "video"
    STAGE = "stage"
    COMPLETE = "complete"
    ERROR = "error"
    PONG = "pong"
