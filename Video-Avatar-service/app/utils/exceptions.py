from __future__ import annotations


class VideoAvatarError(Exception):
    """Base exception for the video avatar service."""

    def __init__(self, detail: str, status_code: int = 500, code: str | None = None) -> None:
        self.detail = detail
        self.status_code = status_code
        self.code = code
        super().__init__(detail)


class AvatarProfileNotFoundError(VideoAvatarError):
    def __init__(self, user_id: str) -> None:
        super().__init__(
            detail=f"No avatar profile found for user '{user_id}'",
            status_code=404,
            code="AVATAR_PROFILE_NOT_FOUND",
        )


class AudioTooLongError(VideoAvatarError):
    def __init__(self, duration: float, max_duration: float) -> None:
        super().__init__(
            detail=f"Audio duration {duration:.1f}s exceeds maximum {max_duration:.1f}s",
            status_code=422,
            code="AUDIO_TOO_LONG",
        )


class AudioTooLargeError(VideoAvatarError):
    def __init__(self, size: int, max_size: int) -> None:
        super().__init__(
            detail=f"Audio size {size} bytes exceeds maximum {max_size} bytes",
            status_code=422,
            code="AUDIO_TOO_LARGE",
        )


class InvalidAudioError(VideoAvatarError):
    def __init__(self, detail: str = "Invalid or unreadable audio data") -> None:
        super().__init__(detail=detail, status_code=422, code="INVALID_AUDIO")


class RendererProviderError(VideoAvatarError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail=detail, status_code=502, code="RENDERER_PROVIDER_ERROR")


class AvatarProfileStorageError(VideoAvatarError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail=detail, status_code=502, code="AVATAR_STORAGE_ERROR")


class MissingAudioInputError(VideoAvatarError):
    def __init__(self) -> None:
        super().__init__(
            detail="Provide either audio_base64 or audio_url",
            status_code=422,
            code="MISSING_AUDIO_INPUT",
        )


class InvalidVideoFormatError(VideoAvatarError):
    def __init__(self, fmt: str) -> None:
        super().__init__(
            detail=f"Unsupported video format: '{fmt}'",
            status_code=422,
            code="INVALID_VIDEO_FORMAT",
        )


class InvalidImageError(VideoAvatarError):
    def __init__(self, detail: str = "Image is not a valid photorealistic photo") -> None:
        super().__init__(detail=detail, status_code=422, code="INVALID_IMAGE")


class ImageTooSmallError(VideoAvatarError):
    def __init__(self, width: int, height: int, min_w: int, min_h: int) -> None:
        super().__init__(
            detail=(
                f"Image resolution {width}x{height} is below the minimum "
                f"{min_w}x{min_h} required for photorealistic avatar rendering"
            ),
            status_code=422,
            code="IMAGE_TOO_SMALL",
        )


class ImageTooLargeError(VideoAvatarError):
    def __init__(self, size: int, max_size: int) -> None:
        super().__init__(
            detail=f"Image file size {size} bytes exceeds maximum {max_size} bytes",
            status_code=422,
            code="IMAGE_TOO_LARGE",
        )


class UnsupportedImageFormatError(VideoAvatarError):
    def __init__(self, fmt: str, allowed: list[str]) -> None:
        super().__init__(
            detail=f"Image format '{fmt}' is not photorealistic-capable; use one of: {', '.join(allowed)}",
            status_code=422,
            code="UNSUPPORTED_IMAGE_FORMAT",
        )


class ImageAspectRatioError(VideoAvatarError):
    def __init__(self, ratio: float, max_ratio: float) -> None:
        super().__init__(
            detail=f"Image aspect ratio {ratio:.1f} exceeds maximum {max_ratio:.1f}; face images should be roughly square or portrait",
            status_code=422,
            code="IMAGE_ASPECT_RATIO",
        )


class ImageNotRGBError(VideoAvatarError):
    def __init__(self, mode: str) -> None:
        super().__init__(
            detail=f"Image color mode '{mode}' is not suitable for photorealistic avatars; provide a full-color RGB/RGBA image",
            status_code=422,
            code="IMAGE_NOT_RGB",
        )


class IngestionDataNotFoundError(VideoAvatarError):
    def __init__(self, user_id: str) -> None:
        super().__init__(
            detail=f"No ingested face images found for user '{user_id}' in the ingestion pipeline",
            status_code=404,
            code="INGESTION_DATA_NOT_FOUND",
        )


class MissingImageInputError(VideoAvatarError):
    def __init__(self) -> None:
        super().__init__(
            detail="Provide source_image_base64 with the user's photorealistic face image",
            status_code=422,
            code="MISSING_IMAGE_INPUT",
        )


class CalibrationVideoTooLargeError(VideoAvatarError):
    def __init__(self, size: int, max_size: int) -> None:
        super().__init__(
            detail=f"Calibration video size {size} bytes exceeds maximum {max_size} bytes",
            status_code=422,
            code="CALIBRATION_VIDEO_TOO_LARGE",
        )


class CalibrationVideoInvalidError(VideoAvatarError):
    def __init__(self, detail: str = "Invalid calibration video") -> None:
        super().__init__(detail=detail, status_code=422, code="CALIBRATION_VIDEO_INVALID")


class FaceScanNotReadyError(VideoAvatarError):
    def __init__(self, user_id: str, status: str) -> None:
        super().__init__(
            detail=f"Face scan for user '{user_id}' is not ready (current status: {status})",
            status_code=409,
            code="FACE_SCAN_NOT_READY",
        )
