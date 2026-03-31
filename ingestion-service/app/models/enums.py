from __future__ import annotations

from enum import Enum


class FileCategory(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"
    TEXT = "text"
    PDF = "pdf"
    DOCUMENT = "document"


class IngestionStatus(str, Enum):
    PENDING = "pending"
    VALIDATING = "validating"
    UPLOADING = "uploading"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingPipeline(str, Enum):
    """Downstream AI pipeline the file should be routed to."""
    TRANSCRIPTION = "transcription"    # Whisper
    FRAME_EXTRACTION = "frame_extraction"  # FFmpeg
    EMBEDDING = "embedding"            # Text/doc embeddings
    OCR = "ocr"                        # PDF/image OCR


MIME_TO_CATEGORY: dict[str, FileCategory] = {
    "video/mp4": FileCategory.VIDEO,
    "video/quicktime": FileCategory.VIDEO,
    "video/x-msvideo": FileCategory.VIDEO,
    "video/webm": FileCategory.VIDEO,
    "video/x-matroska": FileCategory.VIDEO,
    "audio/mpeg": FileCategory.AUDIO,
    "audio/wav": FileCategory.AUDIO,
    "audio/ogg": FileCategory.AUDIO,
    "audio/flac": FileCategory.AUDIO,
    "audio/x-wav": FileCategory.AUDIO,
    "audio/mp4": FileCategory.AUDIO,
    "text/plain": FileCategory.TEXT,
    "text/csv": FileCategory.TEXT,
    "text/markdown": FileCategory.TEXT,
    "application/pdf": FileCategory.PDF,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": FileCategory.DOCUMENT,
}

CATEGORY_TO_PIPELINES: dict[FileCategory, list[ProcessingPipeline]] = {
    FileCategory.VIDEO: [ProcessingPipeline.TRANSCRIPTION, ProcessingPipeline.FRAME_EXTRACTION],
    FileCategory.AUDIO: [ProcessingPipeline.TRANSCRIPTION],
    FileCategory.TEXT: [ProcessingPipeline.EMBEDDING],
    FileCategory.PDF: [ProcessingPipeline.OCR, ProcessingPipeline.EMBEDDING],
    FileCategory.DOCUMENT: [ProcessingPipeline.OCR, ProcessingPipeline.EMBEDDING],
}
