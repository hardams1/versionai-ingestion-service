from __future__ import annotations

import io
import logging
from dataclasses import dataclass

from PIL import Image

from app.config import Settings
from app.utils.exceptions import (
    ImageAspectRatioError,
    ImageNotRGBError,
    ImageTooLargeError,
    ImageTooSmallError,
    InvalidImageError,
    UnsupportedImageFormatError,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImageMetadata:
    width: int
    height: int
    format: str
    mode: str
    file_size: int

    @property
    def aspect_ratio(self) -> float:
        return max(self.width, self.height) / max(1, min(self.width, self.height))


class ImageValidator:
    """Validates that uploaded images meet photorealistic avatar requirements.

    Enforces:
    - Decodable image (not corrupt/fake)
    - Photorealistic-capable format (JPEG, PNG — not GIF, SVG, BMP)
    - Minimum resolution for lip-sync rendering (default 256x256)
    - Maximum resolution to prevent abuse
    - Full-color (RGB/RGBA, not grayscale/palette)
    - Reasonable aspect ratio (face images, not panoramas)
    - Minimum file size (real photos are >5 KB)
    """

    def __init__(self, settings: Settings) -> None:
        self._min_w = settings.min_image_width
        self._min_h = settings.min_image_height
        self._max_w = settings.max_image_width
        self._max_h = settings.max_image_height
        self._min_file_size = settings.min_image_file_size
        self._max_file_size = settings.max_image_file_size
        self._allowed_formats = settings.allowed_image_formats
        self._max_aspect_ratio = settings.max_aspect_ratio

    def validate(self, image_bytes: bytes) -> ImageMetadata:
        """Validate image bytes and return metadata. Raises on any failure."""
        file_size = len(image_bytes)

        if file_size < self._min_file_size:
            raise InvalidImageError(
                f"Image is {file_size} bytes — real photorealistic images "
                f"are at least {self._min_file_size} bytes"
            )

        if file_size > self._max_file_size:
            raise ImageTooLargeError(file_size, self._max_file_size)

        try:
            img = Image.open(io.BytesIO(image_bytes))
            img.verify()
            img = Image.open(io.BytesIO(image_bytes))
        except Exception as exc:
            raise InvalidImageError(
                f"Cannot decode image data — file may be corrupt or not a real image: {exc}"
            ) from exc

        fmt = img.format or "UNKNOWN"
        mode = img.mode
        width, height = img.size

        if fmt not in self._allowed_formats:
            raise UnsupportedImageFormatError(fmt, self._allowed_formats)

        if width < self._min_w or height < self._min_h:
            raise ImageTooSmallError(width, height, self._min_w, self._min_h)

        if width > self._max_w or height > self._max_h:
            raise InvalidImageError(
                f"Image resolution {width}x{height} exceeds maximum {self._max_w}x{self._max_h}"
            )

        if mode not in ("RGB", "RGBA"):
            raise ImageNotRGBError(mode)

        aspect = max(width, height) / max(1, min(width, height))
        if aspect > self._max_aspect_ratio:
            raise ImageAspectRatioError(aspect, self._max_aspect_ratio)

        metadata = ImageMetadata(
            width=width, height=height, format=fmt, mode=mode, file_size=file_size,
        )
        logger.info(
            "Image validated: %dx%d %s %s (%d bytes, ratio=%.2f)",
            width, height, fmt, mode, file_size, aspect,
        )
        return metadata
