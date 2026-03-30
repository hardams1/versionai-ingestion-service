from __future__ import annotations


class BrainError(Exception):
    """Base exception for the AI Brain service."""

    def __init__(self, detail: str, status_code: int = 500, code: str | None = None) -> None:
        self.detail = detail
        self.status_code = status_code
        self.code = code
        super().__init__(detail)


class RetrievalError(BrainError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail=detail, status_code=502, code="RETRIEVAL_ERROR")


class LLMError(BrainError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail=detail, status_code=502, code="LLM_ERROR")


class MemoryError(BrainError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail=detail, status_code=502, code="MEMORY_ERROR")


class SafetyError(BrainError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail=detail, status_code=400, code="SAFETY_BLOCKED")


class PersonalityError(BrainError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail=detail, status_code=400, code="PERSONALITY_ERROR")
