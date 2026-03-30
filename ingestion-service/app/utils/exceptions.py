from __future__ import annotations


class IngestionError(Exception):
    """Base exception for the ingestion service."""

    def __init__(self, detail: str, status_code: int = 500, code: str | None = None) -> None:
        self.detail = detail
        self.status_code = status_code
        self.code = code
        super().__init__(detail)


class FileValidationError(IngestionError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail=detail, status_code=422, code="VALIDATION_ERROR")


class FileTooLargeError(IngestionError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail=detail, status_code=413, code="FILE_TOO_LARGE")


class UnsupportedFileTypeError(IngestionError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail=detail, status_code=415, code="UNSUPPORTED_FILE_TYPE")


class StorageError(IngestionError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail=detail, status_code=502, code="STORAGE_ERROR")


class QueuePublishError(IngestionError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail=detail, status_code=502, code="QUEUE_PUBLISH_ERROR")
