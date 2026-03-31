from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.dependencies import get_tts_engine, get_voice_profile_service, get_voice_profile_store
from app.main import app
from app.services.tts import MockTTSEngine
from app.services.voice_profile import LocalVoiceProfileStore, VoiceProfileService


def _test_settings() -> Settings:
    return Settings(
        tts_provider="mock",
        voice_profile_storage="local",
        voice_profiles_dir="./test_voice_profiles",
        api_key=None,
        environment="development",
    )


@pytest.fixture(autouse=True)
def _clean_profile_dir(tmp_path):
    """Redirect voice profiles to a fresh temp dir for every test."""
    settings = _test_settings()
    settings.voice_profiles_dir = str(tmp_path / "profiles")

    store = LocalVoiceProfileStore(settings)
    svc = VoiceProfileService(store, settings)
    engine = MockTTSEngine()

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_voice_profile_store] = lambda: store
    app.dependency_overrides[get_voice_profile_service] = lambda: svc
    app.dependency_overrides[get_tts_engine] = lambda: engine

    yield

    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
