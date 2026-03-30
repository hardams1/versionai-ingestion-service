from __future__ import annotations

from enum import StrEnum


class FileCategory(StrEnum):
    VIDEO = "video"
    AUDIO = "audio"
    TEXT = "text"
    PDF = "pdf"
    DOCUMENT = "document"


class ProcessingPipeline(StrEnum):
    TRANSCRIPTION = "transcription"
    FRAME_EXTRACTION = "frame_extraction"
    EMBEDDING = "embedding"
    OCR = "ocr"


class ProcessingStatus(StrEnum):
    RECEIVED = "received"
    DOWNLOADING = "downloading"
    EXTRACTING_TEXT = "extracting_text"
    CLEANING = "cleaning"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    STORING = "storing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ProcessingStep(StrEnum):
    """Steps from the simplified input format (image spec)."""
    TRANSCRIBE = "transcribe"
    PARSE = "parse"
    CLEAN = "clean"
    CHUNK = "chunk"
    EMBED = "embed"
    STORE = "store"
