from __future__ import annotations


class VoiceServiceError(Exception):
    """Base exception for the voice service."""

    def __init__(self, detail: str, status_code: int = 500, code: str | None = None) -> None:
        self.detail = detail
        self.status_code = status_code
        self.code = code
        super().__init__(detail)


class VoiceProfileNotFoundError(VoiceServiceError):
    def __init__(self, user_id: str) -> None:
        super().__init__(
            detail=f"No voice profile found for user '{user_id}'",
            status_code=404,
            code="VOICE_PROFILE_NOT_FOUND",
        )


class TextTooLongError(VoiceServiceError):
    def __init__(self, length: int, max_length: int) -> None:
        super().__init__(
            detail=f"Text length {length} exceeds maximum {max_length} characters",
            status_code=422,
            code="TEXT_TOO_LONG",
        )


class TTSProviderError(VoiceServiceError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail=detail, status_code=502, code="TTS_PROVIDER_ERROR")


class InvalidAudioFormatError(VoiceServiceError):
    def __init__(self, fmt: str) -> None:
        super().__init__(
            detail=f"Unsupported audio format: '{fmt}'",
            status_code=422,
            code="INVALID_AUDIO_FORMAT",
        )


class VoiceProfileStorageError(VoiceServiceError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail=detail, status_code=502, code="PROFILE_STORAGE_ERROR")
