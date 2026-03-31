"""Unit tests for the ImageValidator — photorealistic quality gates."""

from __future__ import annotations

import io
import struct

import pytest
from PIL import Image

from app.config import Settings
from app.services.image_validator import ImageValidator
from app.utils.exceptions import (
    ImageAspectRatioError,
    ImageNotRGBError,
    ImageTooLargeError,
    ImageTooSmallError,
    InvalidImageError,
    UnsupportedImageFormatError,
)


def _settings(**overrides) -> Settings:
    defaults = dict(
        renderer_provider="mock",
        avatar_profile_storage="local",
        min_image_width=256,
        min_image_height=256,
        max_image_width=4096,
        max_image_height=4096,
        min_image_file_size=200,
        max_image_file_size=20 * 1024 * 1024,
        max_aspect_ratio=2.0,
    )
    defaults.update(overrides)
    return Settings(**defaults)


def _jpeg(w: int = 512, h: int = 512, mode: str = "RGB", quality: int = 85) -> bytes:
    img = Image.new(mode, (w, h), (128, 90, 70) if mode == "RGB" else 128)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def _png(w: int = 512, h: int = 512, mode: str = "RGB") -> bytes:
    color = (128, 90, 70) if mode in ("RGB", "RGBA") else 128
    img = Image.new(mode, (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestValidFormats:

    def test_jpeg_rgb_valid(self):
        v = ImageValidator(_settings())
        meta = v.validate(_jpeg(512, 512))
        assert meta.format == "JPEG"
        assert meta.mode == "RGB"
        assert meta.width == 512
        assert meta.height == 512
        assert meta.file_size > 200

    def test_png_rgb_valid(self):
        v = ImageValidator(_settings())
        meta = v.validate(_png(300, 300))
        assert meta.format == "PNG"
        assert meta.width == 300

    def test_png_rgba_valid(self):
        v = ImageValidator(_settings())
        meta = v.validate(_png(256, 256, mode="RGBA"))
        assert meta.mode == "RGBA"

    def test_aspect_ratio_property(self):
        v = ImageValidator(_settings())
        meta = v.validate(_jpeg(512, 256))
        assert meta.aspect_ratio == pytest.approx(2.0)


class TestRejectsInvalidFormats:

    def test_gif_rejected(self):
        img = Image.new("RGB", (256, 256), (100, 100, 100))
        buf = io.BytesIO()
        img.save(buf, format="GIF")
        v = ImageValidator(_settings())
        with pytest.raises(UnsupportedImageFormatError):
            v.validate(buf.getvalue())

    def test_bmp_rejected(self):
        img = Image.new("RGB", (256, 256), (100, 100, 100))
        buf = io.BytesIO()
        img.save(buf, format="BMP")
        v = ImageValidator(_settings())
        with pytest.raises(UnsupportedImageFormatError):
            v.validate(buf.getvalue())

    def test_tiff_rejected(self):
        img = Image.new("RGB", (256, 256), (100, 100, 100))
        buf = io.BytesIO()
        img.save(buf, format="TIFF")
        v = ImageValidator(_settings())
        with pytest.raises(UnsupportedImageFormatError):
            v.validate(buf.getvalue())


class TestRejectsCorruptData:

    def test_random_bytes(self):
        v = ImageValidator(_settings())
        with pytest.raises(InvalidImageError):
            v.validate(b"this is definitely not an image" * 100)

    def test_truncated_jpeg_header(self):
        v = ImageValidator(_settings())
        with pytest.raises(InvalidImageError):
            v.validate(b"\xff\xd8\xff\xe0" + b"\x00" * 500)

    def test_empty_bytes(self):
        v = ImageValidator(_settings())
        with pytest.raises(InvalidImageError):
            v.validate(b"")

    def test_html_disguised_as_image(self):
        v = ImageValidator(_settings())
        with pytest.raises(InvalidImageError):
            v.validate(b"<html><body>Not an image</body></html>" + b"\x00" * 500)


class TestResolutionGates:

    def test_too_narrow(self):
        v = ImageValidator(_settings())
        with pytest.raises(ImageTooSmallError):
            v.validate(_jpeg(100, 512))

    def test_too_short(self):
        v = ImageValidator(_settings())
        with pytest.raises(ImageTooSmallError):
            v.validate(_jpeg(512, 100))

    def test_exact_minimum_passes(self):
        v = ImageValidator(_settings())
        meta = v.validate(_jpeg(256, 256))
        assert meta.width == 256
        assert meta.height == 256

    def test_above_maximum_rejected(self):
        v = ImageValidator(_settings(max_image_width=1024, max_image_height=1024))
        with pytest.raises(InvalidImageError):
            v.validate(_jpeg(2048, 2048))


class TestColorMode:

    def test_grayscale_rejected(self):
        v = ImageValidator(_settings())
        with pytest.raises(ImageNotRGBError):
            v.validate(_jpeg(256, 256, mode="L"))

    def test_rgb_accepted(self):
        v = ImageValidator(_settings())
        meta = v.validate(_jpeg(256, 256, mode="RGB"))
        assert meta.mode == "RGB"


class TestAspectRatio:

    def test_extreme_landscape_rejected(self):
        v = ImageValidator(_settings(max_aspect_ratio=2.0))
        with pytest.raises(ImageAspectRatioError):
            v.validate(_jpeg(1024, 256))

    def test_extreme_portrait_rejected(self):
        v = ImageValidator(_settings(max_aspect_ratio=2.0))
        with pytest.raises(ImageAspectRatioError):
            v.validate(_jpeg(256, 1024))

    def test_exact_max_ratio_passes(self):
        v = ImageValidator(_settings(max_aspect_ratio=2.0))
        meta = v.validate(_jpeg(512, 256))
        assert meta.aspect_ratio == pytest.approx(2.0)

    def test_square_always_passes(self):
        v = ImageValidator(_settings(max_aspect_ratio=1.5))
        meta = v.validate(_jpeg(500, 500))
        assert meta.aspect_ratio == pytest.approx(1.0)


class TestFileSize:

    def test_too_small_file_rejected(self):
        v = ImageValidator(_settings(min_image_file_size=100_000))
        with pytest.raises(InvalidImageError):
            v.validate(_jpeg(256, 256))

    def test_too_large_file_rejected(self):
        v = ImageValidator(_settings(max_image_file_size=1000))
        with pytest.raises(ImageTooLargeError):
            v.validate(_jpeg(256, 256))


class TestConfigurableThresholds:

    def test_custom_min_resolution(self):
        v = ImageValidator(_settings(min_image_width=64, min_image_height=64))
        meta = v.validate(_jpeg(64, 64))
        assert meta.width == 64

    def test_custom_allowed_formats(self):
        v = ImageValidator(_settings(allowed_image_formats=["PNG"]))
        with pytest.raises(UnsupportedImageFormatError):
            v.validate(_jpeg(256, 256))
        meta = v.validate(_png(256, 256))
        assert meta.format == "PNG"
