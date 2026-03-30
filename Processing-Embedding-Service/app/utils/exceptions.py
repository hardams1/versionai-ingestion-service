from __future__ import annotations


class ProcessingError(Exception):
    """Base exception for the processing & embedding service."""

    def __init__(self, detail: str, status_code: int = 500, code: str | None = None) -> None:
        self.detail = detail
        self.status_code = status_code
        self.code = code
        super().__init__(detail)


class FileDownloadError(ProcessingError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail=detail, status_code=502, code="FILE_DOWNLOAD_ERROR")


class TextExtractionError(ProcessingError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail=detail, status_code=422, code="TEXT_EXTRACTION_ERROR")


class EmbeddingError(ProcessingError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail=detail, status_code=502, code="EMBEDDING_ERROR")


class VectorStoreError(ProcessingError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail=detail, status_code=502, code="VECTOR_STORE_ERROR")


class IdempotencyConflict(ProcessingError):
    def __init__(self, ingestion_id: str) -> None:
        super().__init__(
            detail=f"Ingestion {ingestion_id} already processed",
            status_code=409,
            code="ALREADY_PROCESSED",
        )
