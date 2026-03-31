from __future__ import annotations


class OrchestratorError(Exception):
    """Base exception for the orchestrator service."""

    def __init__(self, detail: str, status_code: int = 500, code: str | None = None) -> None:
        self.detail = detail
        self.status_code = status_code
        self.code = code
        super().__init__(detail)


class BrainServiceError(OrchestratorError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail=detail, status_code=502, code="BRAIN_SERVICE_ERROR")


class VoiceServiceError(OrchestratorError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail=detail, status_code=502, code="VOICE_SERVICE_ERROR")


class VideoServiceError(OrchestratorError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail=detail, status_code=502, code="VIDEO_SERVICE_ERROR")


class SessionLimitError(OrchestratorError):
    def __init__(self, max_sessions: int) -> None:
        super().__init__(
            detail=f"Maximum concurrent sessions ({max_sessions}) reached",
            status_code=503,
            code="SESSION_LIMIT",
        )


class QueryTooLongError(OrchestratorError):
    def __init__(self, length: int, max_length: int) -> None:
        super().__init__(
            detail=f"Query length {length} exceeds maximum {max_length}",
            status_code=422,
            code="QUERY_TOO_LONG",
        )


class InvalidMessageError(OrchestratorError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail=detail, status_code=400, code="INVALID_MESSAGE")
