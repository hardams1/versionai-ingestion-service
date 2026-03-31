from __future__ import annotations

import base64
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings, get_settings
from app.dependencies import (
    get_avatar_profile_service,
    get_avatar_profile_store,
    get_image_validator,
    get_ingestion_client,
    get_renderer,
)
from app.main import app
from app.services.avatar_profile import AvatarProfileService, LocalAvatarProfileStore
from app.services.image_validator import ImageValidator
from app.services.ingestion_client import IngestionClient
from app.services.renderer import MockRenderer


def _test_settings() -> Settings:
    return Settings(
        renderer_provider="mock",
        avatar_profile_storage="local",
        avatar_profiles_dir="./test_avatar_profiles",
        avatar_images_dir="./test_avatar_images",
        api_key=None,
        environment="development",
        min_image_width=64,
        min_image_height=64,
        min_image_file_size=200,
    )


def create_test_jpeg(width: int = 256, height: int = 256, color: tuple = (128, 90, 70)) -> bytes:
    """Create a minimal valid JPEG image in memory (photorealistic-size RGB)."""
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def create_test_png(width: int = 256, height: int = 256, color: tuple = (128, 90, 70)) -> bytes:
    """Create a minimal valid PNG image in memory."""
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def b64_image(image_bytes: bytes | None = None) -> str:
    """Encode image bytes to base64 (default: 256x256 JPEG)."""
    if image_bytes is None:
        image_bytes = create_test_jpeg()
    return base64.b64encode(image_bytes).decode()


@pytest.fixture(autouse=True)
def _clean_profile_dir(tmp_path):
    """Redirect avatar profiles/images to fresh temp dirs for every test."""
    settings = _test_settings()
    settings.avatar_profiles_dir = str(tmp_path / "profiles")
    settings.avatar_images_dir = str(tmp_path / "images")

    store = LocalAvatarProfileStore(settings)
    validator = ImageValidator(settings)
    svc = AvatarProfileService(store, validator, settings)
    renderer = MockRenderer()

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_avatar_profile_store] = lambda: store
    app.dependency_overrides[get_image_validator] = lambda: validator
    app.dependency_overrides[get_avatar_profile_service] = lambda: svc
    app.dependency_overrides[get_renderer] = lambda: renderer

    yield

    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
