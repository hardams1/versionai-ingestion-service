from __future__ import annotations

import pytest

from app.config import Settings
from app.models.enums import FileCategory
from app.services.validation import FileValidator
from app.utils.exceptions import (
    FileTooLargeError,
    FileValidationError,
    UnsupportedFileTypeError,
)


@pytest.fixture
def validator() -> FileValidator:
    return FileValidator(Settings(
        aws_access_key_id="test",
        aws_secret_access_key="test",
    ))


class TestSizeValidation:
    def test_empty_file_raises(self, validator: FileValidator) -> None:
        with pytest.raises(FileValidationError, match="empty"):
            validator.validate_size(0, "empty.txt")

    def test_oversized_file_raises(self, validator: FileValidator) -> None:
        with pytest.raises(FileTooLargeError, match="exceeding"):
            validator.validate_size(600 * 1024 * 1024, "huge.mp4")

    def test_valid_size_passes(self, validator: FileValidator) -> None:
        validator.validate_size(1024, "ok.txt")


class TestExtensionValidation:
    def test_exe_blocked(self, validator: FileValidator) -> None:
        with pytest.raises(UnsupportedFileTypeError, match="not allowed"):
            validator.validate_extension("malware.exe")

    def test_sh_blocked(self, validator: FileValidator) -> None:
        with pytest.raises(UnsupportedFileTypeError, match="not allowed"):
            validator.validate_extension("script.sh")

    def test_mp4_allowed(self, validator: FileValidator) -> None:
        validator.validate_extension("video.mp4")


class TestMimeValidation:
    def test_valid_mime(self, validator: FileValidator) -> None:
        cat = validator.validate_mime_type("video/mp4", "test.mp4")
        assert cat == FileCategory.VIDEO

    def test_invalid_mime(self, validator: FileValidator) -> None:
        with pytest.raises(UnsupportedFileTypeError, match="not allowed"):
            validator.validate_mime_type("application/x-executable", "bad")


class TestChecksum:
    def test_sha256_deterministic(self) -> None:
        data = b"hello world"
        h1 = FileValidator.compute_sha256(data)
        h2 = FileValidator.compute_sha256(data)
        assert h1 == h2
        assert len(h1) == 64
