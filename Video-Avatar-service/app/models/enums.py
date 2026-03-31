from __future__ import annotations

from enum import Enum


class RendererProvider(str, Enum):
    SYNCLABS = "synclabs"
    D_ID = "d_id"
    MOCK = "mock"


class VideoFormat(str, Enum):
    MP4 = "mp4"
    WEBM = "webm"


class GenerationStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AudioInputType(str, Enum):
    BASE64 = "base64"
    URL = "url"


class ImageFormat(str, Enum):
    JPEG = "JPEG"
    PNG = "PNG"


class ImageSourceType(str, Enum):
    UPLOAD = "upload"
    INGESTION = "ingestion"
    URL = "url"
