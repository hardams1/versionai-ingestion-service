from __future__ import annotations

import hashlib
import logging
import magic
from pathlib import PurePosixPath

from app.config import Settings
from app.models.enums import MIME_TO_CATEGORY, FileCategory
from app.utils.exceptions import (
    FileTooLargeError,
    FileValidationError,
    UnsupportedFileTypeError,
)

logger = logging.getLogger(__name__)

DANGEROUS_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".sh", ".ps1", ".msi", ".dll",
    ".scr", ".com", ".vbs", ".js", ".jar", ".py", ".rb",
}

EXTENSION_TO_MIME: dict[str, str] = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".md": "text/markdown",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class FileValidator:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def validate_size(self, size_bytes: int, filename: str) -> None:
        max_bytes = self._settings.max_upload_size_bytes
        if size_bytes > max_bytes:
            raise FileTooLargeError(
                f"File '{filename}' is {size_bytes} bytes, "
                f"exceeding the {max_bytes} byte limit"
            )
        if size_bytes == 0:
            raise FileValidationError(f"File '{filename}' is empty (0 bytes)")

    def validate_extension(self, filename: str) -> None:
        ext = PurePosixPath(filename).suffix.lower()
        if ext in DANGEROUS_EXTENSIONS:
            raise UnsupportedFileTypeError(
                f"File extension '{ext}' is not allowed for security reasons"
            )

    def detect_mime_type(self, file_header: bytes, filename: str) -> str:
        """
        Detect MIME type from magic bytes, falling back to extension mapping
        when libmagic returns a generic type like application/octet-stream.
        """
        mime = magic.from_buffer(file_header, mime=True)

        generic_types = {"application/octet-stream", "application/x-empty", "inode/x-empty"}
        if mime in generic_types:
            ext = PurePosixPath(filename).suffix.lower()
            ext_mime = EXTENSION_TO_MIME.get(ext)
            if ext_mime:
                logger.info(
                    "Magic detected '%s' for '%s'; falling back to extension-based: '%s'",
                    mime, filename, ext_mime,
                )
                return ext_mime

        return mime

    def validate_mime_type(self, mime_type: str, filename: str) -> FileCategory:
        allowed = self._settings.allowed_mime_types
        if mime_type not in allowed:
            raise UnsupportedFileTypeError(
                f"MIME type '{mime_type}' for file '{filename}' is not allowed. "
                f"Accepted types: {', '.join(allowed)}"
            )
        category = MIME_TO_CATEGORY.get(mime_type)
        if category is None:
            raise UnsupportedFileTypeError(
                f"No category mapping for MIME type '{mime_type}'"
            )
        return category

    @staticmethod
    def compute_sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def validate(
        self, filename: str, file_bytes: bytes
    ) -> tuple[str, FileCategory, str]:
        """
        Run the full validation pipeline.

        Returns (detected_mime_type, file_category, sha256_checksum).
        """
        logger.info("Validating file '%s' (%d bytes)", filename, len(file_bytes))

        self.validate_extension(filename)
        self.validate_size(len(file_bytes), filename)

        header = file_bytes[:4096]
        mime_type = self.detect_mime_type(header, filename)
        category = self.validate_mime_type(mime_type, filename)
        checksum = self.compute_sha256(file_bytes)

        logger.info(
            "File '%s' passed validation: mime=%s category=%s checksum=%s",
            filename, mime_type, category, checksum[:16] + "...",
        )
        return mime_type, category, checksum
