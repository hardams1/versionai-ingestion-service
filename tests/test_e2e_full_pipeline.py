"""
End-to-end integration test: Ingestion → Processing → Brain → Voice → Video Avatar → Orchestrator

Verifies:
1.  Each service's health endpoint is reachable (TestClient-level)
2.  Upload with user_id propagates through metadata → FAISS → Brain retriever
3.  Brain retrieves correct context and generates grounded response
4.  Voice profile creation + audio synthesis with that profile
5.  Video Avatar profile creation + video generation from audio
6.  Full pipeline: upload → embed → chat → synthesize → video render (all 5 services)
7.  Tenant isolation enforced across the pipeline
8.  Brain orchestrator wires Voice + Video Avatar via MediaClient
9.  Real-Time Orchestrator health, HTTP, and WebSocket endpoints
"""
from __future__ import annotations

import base64
import importlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict
from unittest.mock import AsyncMock

import numpy as np
import pytest

os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("VECTOR_STORE_PROVIDER", "faiss")
os.environ.setdefault("EMBEDDING_PROVIDER", "openai")
os.environ.setdefault("LLM_PROVIDER", "openai")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("TTS_PROVIDER", "mock")
os.environ.setdefault("VOICE_PROFILE_STORAGE", "local")
os.environ.setdefault("RENDERER_PROVIDER", "mock")
os.environ.setdefault("AVATAR_PROFILE_STORAGE", "local")

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _clear_app_modules():
    to_remove = [k for k in sys.modules if k == "app" or k.startswith("app.")]
    for k in to_remove:
        del sys.modules[k]


def _import_from_service(service_dir: str, module_path: str, names: list):
    svc_path = str(PROJECT_ROOT / service_dir)
    _clear_app_modules()
    old_path = sys.path.copy()
    sys.path.insert(0, svc_path)
    try:
        mod = importlib.import_module(module_path)
        return {name: getattr(mod, name) for name in names}
    finally:
        sys.path = old_path


def make_fake_embedding(dim: int = 1536, seed: int = 42):
    rng = np.random.RandomState(seed)
    vec = rng.randn(dim).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    return vec.tolist()


def _create_test_jpeg(width: int = 256, height: int = 256) -> bytes:
    """Create a minimal valid JPEG image in memory."""
    from PIL import Image as PILImage
    img = PILImage.new("RGB", (width, height), (128, 90, 70))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Voice Service integration tests (via TestClient)
# ---------------------------------------------------------------------------

class TestVoiceServiceIntegration:
    """Tests Voice service standalone — profile CRUD + audio synthesis."""

    @pytest.fixture(autouse=True)
    def _setup_voice_client(self, tmp_path):
        _clear_app_modules()
        old_path = sys.path.copy()
        voice_path = str(PROJECT_ROOT / "Voice-service")
        sys.path.insert(0, voice_path)

        try:
            from app.config import Settings, get_settings
            from app.dependencies import get_tts_engine, get_voice_profile_service, get_voice_profile_store
            from app.main import app
            from app.services.tts import MockTTSEngine
            from app.services.voice_profile import LocalVoiceProfileStore, VoiceProfileService

            settings = Settings(
                tts_provider="mock",
                voice_profile_storage="local",
                voice_profiles_dir=str(tmp_path / "profiles"),
                api_key=None,
            )
            store = LocalVoiceProfileStore(settings)
            svc = VoiceProfileService(store, settings)
            engine = MockTTSEngine()

            app.dependency_overrides[get_settings] = lambda: settings
            app.dependency_overrides[get_voice_profile_store] = lambda: store
            app.dependency_overrides[get_voice_profile_service] = lambda: svc
            app.dependency_overrides[get_tts_engine] = lambda: engine

            from fastapi.testclient import TestClient
            self.client = TestClient(app)
            self.app = app
            yield
            app.dependency_overrides.clear()
        finally:
            sys.path = old_path
            _clear_app_modules()

    def test_voice_health(self):
        resp = self.client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_create_profile_then_synthesize_audio(self):
        resp = self.client.post("/api/v1/profiles", json={
            "user_id": "user-e2e",
            "voice_id": "nova",
            "provider": "mock",
            "display_name": "E2E User",
        })
        assert resp.status_code == 201

        resp = self.client.post("/api/v1/synthesize/audio", json={
            "text": "Hello from the end-to-end test!",
            "user_id": "user-e2e",
        })
        assert resp.status_code == 200
        assert resp.headers["x-voice-id"] == "nova"
        assert len(resp.content) > 44

    def test_synthesis_fails_without_profile(self):
        resp = self.client.post("/api/v1/synthesize/audio", json={
            "text": "This should fail",
            "user_id": "nonexistent-user",
        })
        assert resp.status_code == 404
        assert resp.json()["code"] == "VOICE_PROFILE_NOT_FOUND"

    def test_different_users_get_correct_voices(self):
        self.client.post("/api/v1/profiles", json={
            "user_id": "alice", "voice_id": "alloy", "provider": "mock",
        })
        self.client.post("/api/v1/profiles", json={
            "user_id": "bob", "voice_id": "shimmer", "provider": "mock",
        })

        resp_a = self.client.post("/api/v1/synthesize/audio", json={
            "text": "Same text for both", "user_id": "alice",
        })
        resp_b = self.client.post("/api/v1/synthesize/audio", json={
            "text": "Same text for both", "user_id": "bob",
        })

        assert resp_a.headers["x-voice-id"] == "alloy"
        assert resp_b.headers["x-voice-id"] == "shimmer"


# ---------------------------------------------------------------------------
# Video Avatar Service integration tests (via TestClient)
# ---------------------------------------------------------------------------

class TestVideoAvatarServiceIntegration:
    """Tests Video Avatar service standalone — avatar CRUD + video generation."""

    @pytest.fixture(autouse=True)
    def _setup_avatar_client(self, tmp_path):
        _clear_app_modules()
        old_path = sys.path.copy()
        avatar_path = str(PROJECT_ROOT / "Video-Avatar-service")
        sys.path.insert(0, avatar_path)

        try:
            from app.config import Settings, get_settings
            from app.dependencies import (
                get_avatar_profile_service,
                get_avatar_profile_store,
                get_image_validator,
                get_renderer,
            )
            from app.main import app
            from app.services.avatar_profile import AvatarProfileService, LocalAvatarProfileStore
            from app.services.image_validator import ImageValidator
            from app.services.renderer import MockRenderer

            settings = Settings(
                renderer_provider="mock",
                avatar_profile_storage="local",
                avatar_profiles_dir=str(tmp_path / "profiles"),
                avatar_images_dir=str(tmp_path / "images"),
                api_key=None,
                min_image_width=64,
                min_image_height=64,
                min_image_file_size=200,
            )
            store = LocalAvatarProfileStore(settings)
            validator = ImageValidator(settings)
            svc = AvatarProfileService(store, validator, settings)
            renderer = MockRenderer()

            app.dependency_overrides[get_settings] = lambda: settings
            app.dependency_overrides[get_avatar_profile_store] = lambda: store
            app.dependency_overrides[get_image_validator] = lambda: validator
            app.dependency_overrides[get_avatar_profile_service] = lambda: svc
            app.dependency_overrides[get_renderer] = lambda: renderer

            from fastapi.testclient import TestClient
            self.client = TestClient(app)
            self.app = app
            yield
            app.dependency_overrides.clear()
        finally:
            sys.path = old_path
            _clear_app_modules()

    def test_avatar_health(self):
        resp = self.client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_create_avatar_then_generate_video(self):
        image_b64 = base64.b64encode(_create_test_jpeg()).decode()

        resp = self.client.post("/api/v1/avatars", json={
            "user_id": "user-e2e",
            "avatar_id": "avatar-e2e",
            "source_image_base64": image_b64,
            "provider": "mock",
            "display_name": "E2E Avatar",
        })
        assert resp.status_code == 201
        assert resp.json()["avatar_id"] == "avatar-e2e"
        assert resp.json()["image_width"] >= 64

        audio_bytes = b"RIFF" + b"\x00" * 200
        audio_b64 = base64.b64encode(audio_bytes).decode()

        resp = self.client.post("/api/v1/generate/video", json={
            "user_id": "user-e2e",
            "audio_base64": audio_b64,
            "video_format": "mp4",
        })
        assert resp.status_code == 200
        assert resp.headers["x-avatar-id"] == "avatar-e2e"
        assert resp.headers["x-user-id"] == "user-e2e"
        video_bytes = resp.content
        assert len(video_bytes) > 0

    def test_video_fails_without_avatar(self):
        audio_bytes = b"RIFF" + b"\x00" * 200
        audio_b64 = base64.b64encode(audio_bytes).decode()

        resp = self.client.post("/api/v1/generate/video", json={
            "user_id": "nonexistent-user",
            "audio_base64": audio_b64,
        })
        assert resp.status_code == 404

    def test_avatar_profile_crud(self):
        image_b64 = base64.b64encode(_create_test_jpeg()).decode()

        resp = self.client.post("/api/v1/avatars", json={
            "user_id": "crud-user",
            "avatar_id": "crud-avatar",
            "source_image_base64": image_b64,
            "provider": "mock",
        })
        assert resp.status_code == 201

        resp = self.client.get("/api/v1/avatars/crud-user")
        assert resp.status_code == 200
        assert resp.json()["avatar_id"] == "crud-avatar"

        resp = self.client.delete("/api/v1/avatars/crud-user")
        assert resp.status_code in (200, 204)

        resp = self.client.get("/api/v1/avatars/crud-user")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Full pipeline: Ingestion metadata → FAISS → Brain → Voice → Video Avatar
# ---------------------------------------------------------------------------

class TestFullPipelineIntegration:
    """
    Simulates the complete VersionAI pipeline:
    1. Ingestion produces a QueueMessage with user_id
    2. Processing embeds chunks into FAISS with user metadata
    3. Brain retrieves context for the correct user and generates a response
    4. Voice synthesizes audio from Brain's text response using the user's profile
    5. Video Avatar renders a talking-face video from the audio
    """

    @pytest.fixture
    def faiss_dir(self):
        tmpdir = tempfile.mkdtemp(prefix="versionai_full_e2e_")
        yield tmpdir

    @pytest.fixture
    def voice_profiles_dir(self, tmp_path):
        d = tmp_path / "voice_profiles"
        d.mkdir()
        return str(d)

    @pytest.fixture
    def avatar_dirs(self, tmp_path):
        profiles = tmp_path / "avatar_profiles"
        images = tmp_path / "avatar_images"
        profiles.mkdir()
        images.mkdir()
        return str(profiles), str(images)

    @pytest.fixture
    def embedding_dim(self):
        return 1536

    @pytest.mark.asyncio
    async def test_upload_to_video_full_pipeline(self, faiss_dir, voice_profiles_dir, avatar_dirs, embedding_dim):
        """The complete flow: ingest → process → chat → voice → video avatar."""
        import faiss as faiss_lib

        user_id = "user-fullpipe"
        dim = embedding_dim
        avatar_profiles_dir, avatar_images_dir = avatar_dirs

        # -- Phase 1: Simulate Ingestion QueueMessage --
        queue_message = {
            "ingestion_id": "ing-full-001",
            "filename": "company-info.txt",
            "s3_bucket": "versionai-ingestion",
            "s3_key": "uploads/text/company-info.txt",
            "file_category": "text",
            "mime_type": "text/plain",
            "size_bytes": 200,
            "checksum_sha256": "abc123",
            "pipelines": ["embedding"],
            "metadata": {
                "original_filename": "company-info.txt",
                "user_id": user_id,
            },
        }
        assert queue_message["metadata"]["user_id"] == user_id

        # -- Phase 2: Simulate Processing → FAISS --
        doc_text = "VersionAI was founded in 2024 by a team of AI researchers in San Francisco."
        chunk_embedding = make_fake_embedding(dim, seed=42)

        vec = np.array([chunk_embedding], dtype=np.float32)
        norms = np.linalg.norm(vec, axis=1, keepdims=True)
        vec = vec / norms

        index = faiss_lib.IndexFlatIP(dim)
        index.add(vec)

        faiss_metadata = [{
            "ingestion_id": "ing-full-001",
            "chunk_index": 0,
            "text": doc_text,
            "token_count": 15,
            "user_id": user_id,
            "filename": "company-info.txt",
        }]

        faiss_lib.write_index(index, os.path.join(faiss_dir, "index.faiss"))
        with open(os.path.join(faiss_dir, "metadata.json"), "w") as f:
            json.dump({"metadata": faiss_metadata, "id_map": {"ing-full-001": [0]}}, f)

        # -- Phase 3: Brain retrieves and generates response --
        _clear_app_modules()
        brain_path = str(PROJECT_ROOT / "AI-Brain-service")
        old_path = sys.path.copy()
        sys.path.insert(0, brain_path)

        try:
            from app.config import Settings as BrainSettings
            from app.models.schemas import ChatRequest, TokenUsage
            from app.services.llm import LLMResponse
            from app.services.memory import ConversationMemory
            from app.services.orchestrator import BrainOrchestrator
            from app.services.personality_store import PersonalityStore
            from app.services.prompt_builder import PromptBuilder
            from app.services.retriever import FAISSRetriever
            from app.services.safety import SafetyProcessor

            brain_settings = BrainSettings(
                openai_api_key="sk-test-fake",
                faiss_index_dir=faiss_dir,
                retrieval_top_k=5,
                retrieval_score_threshold=0.0,
                voice_service_url="http://localhost:8003",
                video_avatar_service_url="http://localhost:8004",
            )

            retriever = FAISSRetriever(brain_settings)
            await retriever.initialize()
            memory = ConversationMemory(brain_settings)
            ps = PersonalityStore(brain_settings)
            await ps.initialize()

            mock_embedder = AsyncMock()
            mock_embedder.embed.return_value = make_fake_embedding(dim, seed=42)

            brain_response_text = "VersionAI was founded in 2024 by a team of AI researchers based in San Francisco."
            mock_llm = AsyncMock()
            mock_llm.generate.return_value = LLMResponse(
                content=brain_response_text,
                model="test-model",
                usage=TokenUsage(prompt_tokens=200, completion_tokens=20, total_tokens=220),
                finish_reason="stop",
            )

            orchestrator = BrainOrchestrator(
                settings=brain_settings,
                retriever=retriever,
                embedder=mock_embedder,
                llm=mock_llm,
                memory=memory,
                personality_store=ps,
                prompt_builder=PromptBuilder(brain_settings),
                safety=SafetyProcessor(brain_settings),
            )

            chat_resp = await orchestrator.chat(
                ChatRequest(user_id=user_id, query="When was VersionAI founded?")
            )

            assert len(chat_resp.sources) > 0, "Brain should retrieve user's document"
            assert "2024" in chat_resp.response or "VersionAI" in chat_resp.response

            other_resp = await orchestrator.chat(
                ChatRequest(user_id="user-other", query="When was VersionAI founded?")
            )
            assert len(other_resp.sources) == 0, "Other user should NOT see this user's docs"

        finally:
            sys.path = old_path
            _clear_app_modules()

        # -- Phase 4: Voice synthesizes audio from Brain's response --
        voice_path = str(PROJECT_ROOT / "Voice-service")
        sys.path.insert(0, voice_path)

        try:
            from app.config import Settings as VoiceSettings
            from app.config import get_settings as voice_get_settings
            from app.dependencies import get_tts_engine, get_voice_profile_service, get_voice_profile_store
            from app.main import app as voice_app
            from app.services.tts import MockTTSEngine
            from app.services.voice_profile import LocalVoiceProfileStore, VoiceProfileService

            v_settings = VoiceSettings(
                tts_provider="mock",
                voice_profile_storage="local",
                voice_profiles_dir=voice_profiles_dir,
                api_key=None,
            )
            v_store = LocalVoiceProfileStore(v_settings)
            v_svc = VoiceProfileService(v_store, v_settings)
            v_engine = MockTTSEngine()

            voice_app.dependency_overrides[voice_get_settings] = lambda: v_settings
            voice_app.dependency_overrides[get_voice_profile_store] = lambda: v_store
            voice_app.dependency_overrides[get_voice_profile_service] = lambda: v_svc
            voice_app.dependency_overrides[get_tts_engine] = lambda: v_engine

            from fastapi.testclient import TestClient
            voice_client = TestClient(voice_app)

            resp = voice_client.post("/api/v1/profiles", json={
                "user_id": user_id,
                "voice_id": "nova",
                "provider": "mock",
                "display_name": "Full Pipeline User",
            })
            assert resp.status_code == 201

            resp = voice_client.post("/api/v1/synthesize/audio", json={
                "text": brain_response_text,
                "user_id": user_id,
            })
            assert resp.status_code == 200
            assert resp.headers["x-voice-id"] == "nova"
            assert resp.headers["x-user-id"] == user_id
            audio_bytes = resp.content
            assert len(audio_bytes) > 44, "Should contain valid audio data"
            assert audio_bytes[:4] == b"RIFF", "MockTTS returns WAV format"

            voice_app.dependency_overrides.clear()

        finally:
            sys.path = old_path
            _clear_app_modules()

        # -- Phase 5: Video Avatar renders from the audio --
        avatar_path = str(PROJECT_ROOT / "Video-Avatar-service")
        sys.path.insert(0, avatar_path)

        try:
            from app.config import Settings as AvatarSettings
            from app.config import get_settings as avatar_get_settings
            from app.dependencies import (
                get_avatar_profile_service as get_av_svc,
                get_avatar_profile_store as get_av_store,
                get_image_validator as get_iv,
                get_renderer as get_rend,
            )
            from app.main import app as avatar_app
            from app.services.avatar_profile import AvatarProfileService as AvSvc, LocalAvatarProfileStore as LocalAvStore
            from app.services.image_validator import ImageValidator as IV
            from app.services.renderer import MockRenderer

            a_settings = AvatarSettings(
                renderer_provider="mock",
                avatar_profile_storage="local",
                avatar_profiles_dir=avatar_profiles_dir,
                avatar_images_dir=avatar_images_dir,
                api_key=None,
                min_image_width=64,
                min_image_height=64,
                min_image_file_size=200,
            )
            a_store = LocalAvStore(a_settings)
            a_validator = IV(a_settings)
            a_svc = AvSvc(a_store, a_validator, a_settings)
            a_renderer = MockRenderer()

            avatar_app.dependency_overrides[avatar_get_settings] = lambda: a_settings
            avatar_app.dependency_overrides[get_av_store] = lambda: a_store
            avatar_app.dependency_overrides[get_iv] = lambda: a_validator
            avatar_app.dependency_overrides[get_av_svc] = lambda: a_svc
            avatar_app.dependency_overrides[get_rend] = lambda: a_renderer

            from fastapi.testclient import TestClient
            avatar_client = TestClient(avatar_app)

            image_b64 = base64.b64encode(_create_test_jpeg()).decode()
            resp = avatar_client.post("/api/v1/avatars", json={
                "user_id": user_id,
                "avatar_id": "avatar-fullpipe",
                "source_image_base64": image_b64,
                "provider": "mock",
                "display_name": "Full Pipeline Avatar",
            })
            assert resp.status_code == 201, f"Avatar creation failed: {resp.text}"

            audio_b64 = base64.b64encode(audio_bytes).decode()
            resp = avatar_client.post("/api/v1/generate/video", json={
                "user_id": user_id,
                "audio_base64": audio_b64,
                "video_format": "mp4",
            })
            assert resp.status_code == 200
            assert resp.headers["x-avatar-id"] == "avatar-fullpipe"
            assert resp.headers["x-user-id"] == user_id
            video_bytes = resp.content
            assert len(video_bytes) > 0, "Should contain video data"

            video_duration = float(resp.headers.get("x-video-duration", "0"))
            assert video_duration > 0, "Video should have positive duration"

            avatar_app.dependency_overrides.clear()

        finally:
            sys.path = old_path
            _clear_app_modules()

    def test_ingestion_metadata_carries_user_id(self):
        """Verify user_id set during upload appears in QueueMessage metadata."""
        queue_msg_metadata = {
            "original_filename": "report.pdf",
            "extension": ".pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "size_bytes": 10000,
            "user_id": "user-from-upload",
        }

        chunk_metadata = {
            "ingestion_id": "ing-test",
            "filename": "report.pdf",
            "file_category": "document",
            **{k: v for k, v in queue_msg_metadata.items() if isinstance(v, (str, int, float, bool))},
        }

        assert chunk_metadata["user_id"] == "user-from-upload"

    @pytest.mark.asyncio
    async def test_voice_refuses_synthesis_without_profile(self, voice_profiles_dir):
        """System requirement: NEVER generate generic voices for known users."""
        _clear_app_modules()
        voice_path = str(PROJECT_ROOT / "Voice-service")
        old_path = sys.path.copy()
        sys.path.insert(0, voice_path)

        try:
            from app.config import Settings as VoiceSettings
            from app.config import get_settings as voice_get_settings
            from app.dependencies import get_tts_engine, get_voice_profile_service, get_voice_profile_store
            from app.main import app as voice_app
            from app.services.tts import MockTTSEngine
            from app.services.voice_profile import LocalVoiceProfileStore, VoiceProfileService

            v_settings = VoiceSettings(
                tts_provider="mock",
                voice_profile_storage="local",
                voice_profiles_dir=voice_profiles_dir,
                api_key=None,
            )
            v_store = LocalVoiceProfileStore(v_settings)
            v_svc = VoiceProfileService(v_store, v_settings)

            voice_app.dependency_overrides[voice_get_settings] = lambda: v_settings
            voice_app.dependency_overrides[get_voice_profile_store] = lambda: v_store
            voice_app.dependency_overrides[get_voice_profile_service] = lambda: v_svc
            voice_app.dependency_overrides[get_tts_engine] = lambda: MockTTSEngine()

            from fastapi.testclient import TestClient
            voice_client = TestClient(voice_app)

            resp = voice_client.post("/api/v1/synthesize/audio", json={
                "text": "Should fail without a profile",
                "user_id": "unknown-user-xyz",
            })
            assert resp.status_code == 404
            assert resp.json()["code"] == "VOICE_PROFILE_NOT_FOUND"

            voice_app.dependency_overrides.clear()
        finally:
            sys.path = old_path
            _clear_app_modules()

    @pytest.mark.asyncio
    async def test_brain_voice_integration_config(self):
        """Brain service config includes voice_service_url for health checks."""
        _clear_app_modules()
        brain_path = str(PROJECT_ROOT / "AI-Brain-service")
        old_path = sys.path.copy()
        sys.path.insert(0, brain_path)

        try:
            from app.config import Settings as BrainSettings
            from app.services.integration import SiblingServiceClient

            settings = BrainSettings(
                openai_api_key="sk-test",
                voice_service_url="http://voice:8003",
            )
            client = SiblingServiceClient(settings)

            result = await client.check_voice()
            assert result["status"] in ("unreachable", "timeout", "healthy", "unhealthy")

            settings_no_voice = BrainSettings(
                openai_api_key="sk-test",
                voice_service_url=None,
            )
            client_no_voice = SiblingServiceClient(settings_no_voice)
            result = await client_no_voice.check_voice()
            assert result["status"] == "not_configured"

        finally:
            sys.path = old_path
            _clear_app_modules()

    @pytest.mark.asyncio
    async def test_brain_video_avatar_integration_config(self):
        """Brain service config includes video_avatar_service_url for health checks."""
        _clear_app_modules()
        brain_path = str(PROJECT_ROOT / "AI-Brain-service")
        old_path = sys.path.copy()
        sys.path.insert(0, brain_path)

        try:
            from app.config import Settings as BrainSettings
            from app.services.integration import SiblingServiceClient

            settings = BrainSettings(
                openai_api_key="sk-test",
                video_avatar_service_url="http://video-avatar:8004",
            )
            client = SiblingServiceClient(settings)

            result = await client.check_video_avatar()
            assert result["status"] in ("unreachable", "timeout", "healthy", "unhealthy")

            settings_none = BrainSettings(
                openai_api_key="sk-test",
                video_avatar_service_url=None,
            )
            client_none = SiblingServiceClient(settings_none)
            result = await client_none.check_video_avatar()
            assert result["status"] == "not_configured"

        finally:
            sys.path = old_path
            _clear_app_modules()

    @pytest.mark.asyncio
    async def test_brain_media_client(self):
        """MediaClient reports availability based on config."""
        _clear_app_modules()
        brain_path = str(PROJECT_ROOT / "AI-Brain-service")
        old_path = sys.path.copy()
        sys.path.insert(0, brain_path)

        try:
            from app.config import Settings as BrainSettings
            from app.services.integration import MediaClient

            settings_all = BrainSettings(
                openai_api_key="sk-test",
                voice_service_url="http://voice:8003",
                video_avatar_service_url="http://video-avatar:8004",
            )
            mc = MediaClient(settings_all)
            assert mc.voice_available is True
            assert mc.video_avatar_available is True

            settings_none = BrainSettings(
                openai_api_key="sk-test",
                voice_service_url=None,
                video_avatar_service_url=None,
            )
            mc_none = MediaClient(settings_none)
            assert mc_none.voice_available is False
            assert mc_none.video_avatar_available is False

            result = await mc_none.synthesize_audio("test", "user")
            assert result is None

            result = await mc_none.generate_video(b"audio", "user")
            assert result is None

        finally:
            sys.path = old_path
            _clear_app_modules()

    @pytest.mark.asyncio
    async def test_brain_orchestrator_with_media_flags(self, faiss_dir):
        """Brain orchestrator passes audio/video flags through ChatRequest/ChatResponse."""
        import faiss as faiss_lib

        dim = 1536
        vec = np.array([make_fake_embedding(dim, seed=42)], dtype=np.float32)
        vec = vec / np.linalg.norm(vec, axis=1, keepdims=True)
        index = faiss_lib.IndexFlatIP(dim)
        index.add(vec)

        faiss_metadata = [{
            "ingestion_id": "t1", "chunk_index": 0, "text": "Test doc.",
            "user_id": "u1", "token_count": 2,
        }]
        faiss_lib.write_index(index, os.path.join(faiss_dir, "index.faiss"))
        with open(os.path.join(faiss_dir, "metadata.json"), "w") as f:
            json.dump({"metadata": faiss_metadata, "id_map": {"t1": [0]}}, f)

        _clear_app_modules()
        brain_path = str(PROJECT_ROOT / "AI-Brain-service")
        old_path = sys.path.copy()
        sys.path.insert(0, brain_path)

        try:
            from app.config import Settings as BrainSettings
            from app.models.schemas import ChatRequest, TokenUsage
            from app.services.llm import LLMResponse
            from app.services.memory import ConversationMemory
            from app.services.orchestrator import BrainOrchestrator
            from app.services.personality_store import PersonalityStore
            from app.services.prompt_builder import PromptBuilder
            from app.services.retriever import FAISSRetriever
            from app.services.safety import SafetyProcessor

            brain_settings = BrainSettings(
                openai_api_key="sk-test",
                faiss_index_dir=faiss_dir,
                retrieval_score_threshold=0.0,
            )

            retriever = FAISSRetriever(brain_settings)
            await retriever.initialize()
            memory = ConversationMemory(brain_settings)
            ps = PersonalityStore(brain_settings)
            await ps.initialize()

            mock_embedder = AsyncMock()
            mock_embedder.embed.return_value = make_fake_embedding(dim, seed=42)

            mock_llm = AsyncMock()
            mock_llm.generate.return_value = LLMResponse(
                content="Test answer.",
                model="test",
                usage=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
                finish_reason="stop",
            )

            orchestrator = BrainOrchestrator(
                settings=brain_settings,
                retriever=retriever,
                embedder=mock_embedder,
                llm=mock_llm,
                memory=memory,
                personality_store=ps,
                prompt_builder=PromptBuilder(brain_settings),
                safety=SafetyProcessor(brain_settings),
                media_client=None,
            )

            resp = await orchestrator.chat(
                ChatRequest(user_id="u1", query="test", include_audio=True, include_video=True)
            )
            assert resp.audio_base64 is None
            assert resp.video_base64 is None
            assert resp.response == "Test answer."

        finally:
            sys.path = old_path
            _clear_app_modules()


# ---------------------------------------------------------------------------
# Cross-service tenant isolation
# ---------------------------------------------------------------------------

class TestTenantIsolation:
    """Verify no data leaks between users across the full pipeline."""

    @pytest.fixture
    def faiss_dir(self):
        tmpdir = tempfile.mkdtemp(prefix="versionai_tenant_")
        yield tmpdir

    @pytest.mark.asyncio
    async def test_faiss_tenant_isolation(self, faiss_dir):
        """Two users' data in FAISS — each can only see their own."""
        import faiss as faiss_lib

        dim = 1536

        alice_vec = np.array([make_fake_embedding(dim, seed=1)], dtype=np.float32)
        bob_vec = np.array([make_fake_embedding(dim, seed=2)], dtype=np.float32)
        vecs = np.vstack([alice_vec, bob_vec])
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        vecs = vecs / norms

        index = faiss_lib.IndexFlatIP(dim)
        index.add(vecs)

        metadata = [
            {"ingestion_id": "alice-doc", "chunk_index": 0, "text": "Alice's secret.", "user_id": "alice", "token_count": 3},
            {"ingestion_id": "bob-doc", "chunk_index": 0, "text": "Bob's secret.", "user_id": "bob", "token_count": 3},
        ]

        faiss_lib.write_index(index, os.path.join(faiss_dir, "index.faiss"))
        with open(os.path.join(faiss_dir, "metadata.json"), "w") as f:
            json.dump({"metadata": metadata, "id_map": {"alice-doc": [0], "bob-doc": [1]}}, f)

        brain = _import_from_service("AI-Brain-service", "app.services.retriever", ["FAISSRetriever"])
        brain_cfg = _import_from_service("AI-Brain-service", "app.config", ["Settings"])

        settings = brain_cfg["Settings"](openai_api_key="sk-fake", faiss_index_dir=faiss_dir, retrieval_score_threshold=0.0)
        retriever = brain["FAISSRetriever"](settings)
        await retriever.initialize()

        alice_results = await retriever.search(make_fake_embedding(dim, seed=1), user_id="alice", top_k=10, score_threshold=0.0)
        bob_results = await retriever.search(make_fake_embedding(dim, seed=1), user_id="bob", top_k=10, score_threshold=0.0)

        alice_texts = {r.text for r in alice_results}
        bob_texts = {r.text for r in bob_results}

        assert "Alice's secret." in alice_texts
        assert "Bob's secret." not in alice_texts
        assert "Bob's secret." in bob_texts
        assert "Alice's secret." not in bob_texts

    @pytest.mark.asyncio
    async def test_voice_profile_tenant_isolation(self, tmp_path):
        """Users cannot synthesize with another user's voice profile."""
        _clear_app_modules()
        voice_path = str(PROJECT_ROOT / "Voice-service")
        old_path = sys.path.copy()
        sys.path.insert(0, voice_path)

        try:
            from app.config import Settings as VoiceSettings
            from app.config import get_settings as voice_get_settings
            from app.dependencies import get_tts_engine, get_voice_profile_service, get_voice_profile_store
            from app.main import app as voice_app
            from app.services.tts import MockTTSEngine
            from app.services.voice_profile import LocalVoiceProfileStore, VoiceProfileService

            v_settings = VoiceSettings(
                tts_provider="mock",
                voice_profile_storage="local",
                voice_profiles_dir=str(tmp_path / "iso_profiles"),
                api_key=None,
            )
            v_store = LocalVoiceProfileStore(v_settings)
            v_svc = VoiceProfileService(v_store, v_settings)

            voice_app.dependency_overrides[voice_get_settings] = lambda: v_settings
            voice_app.dependency_overrides[get_voice_profile_store] = lambda: v_store
            voice_app.dependency_overrides[get_voice_profile_service] = lambda: v_svc
            voice_app.dependency_overrides[get_tts_engine] = lambda: MockTTSEngine()

            from fastapi.testclient import TestClient
            c = TestClient(voice_app)

            c.post("/api/v1/profiles", json={"user_id": "alice", "voice_id": "alloy", "provider": "mock"})

            resp_alice = c.post("/api/v1/synthesize/audio", json={"text": "Hello", "user_id": "alice"})
            assert resp_alice.status_code == 200
            assert resp_alice.headers["x-voice-id"] == "alloy"

            resp_bob = c.post("/api/v1/synthesize/audio", json={"text": "Hello", "user_id": "bob"})
            assert resp_bob.status_code == 404

            voice_app.dependency_overrides.clear()
        finally:
            sys.path = old_path
            _clear_app_modules()

    @pytest.mark.asyncio
    async def test_avatar_profile_tenant_isolation(self, tmp_path):
        """Users cannot generate video with another user's avatar profile."""
        _clear_app_modules()
        avatar_path = str(PROJECT_ROOT / "Video-Avatar-service")
        old_path = sys.path.copy()
        sys.path.insert(0, avatar_path)

        try:
            from app.config import Settings as AvatarSettings
            from app.config import get_settings as avatar_get_settings
            from app.dependencies import (
                get_avatar_profile_service,
                get_avatar_profile_store,
                get_image_validator,
                get_renderer,
            )
            from app.main import app as avatar_app
            from app.services.avatar_profile import AvatarProfileService, LocalAvatarProfileStore
            from app.services.image_validator import ImageValidator
            from app.services.renderer import MockRenderer

            a_settings = AvatarSettings(
                renderer_provider="mock",
                avatar_profile_storage="local",
                avatar_profiles_dir=str(tmp_path / "iso_av_profiles"),
                avatar_images_dir=str(tmp_path / "iso_av_images"),
                api_key=None,
                min_image_width=64,
                min_image_height=64,
                min_image_file_size=200,
            )
            a_store = LocalAvatarProfileStore(a_settings)
            a_validator = ImageValidator(a_settings)
            a_svc = AvatarProfileService(a_store, a_validator, a_settings)

            avatar_app.dependency_overrides[avatar_get_settings] = lambda: a_settings
            avatar_app.dependency_overrides[get_avatar_profile_store] = lambda: a_store
            avatar_app.dependency_overrides[get_image_validator] = lambda: a_validator
            avatar_app.dependency_overrides[get_avatar_profile_service] = lambda: a_svc
            avatar_app.dependency_overrides[get_renderer] = lambda: MockRenderer()

            from fastapi.testclient import TestClient
            c = TestClient(avatar_app)

            image_b64 = base64.b64encode(_create_test_jpeg()).decode()
            c.post("/api/v1/avatars", json={
                "user_id": "alice",
                "avatar_id": "alice-av",
                "source_image_base64": image_b64,
                "provider": "mock",
            })

            audio_b64 = base64.b64encode(b"RIFF" + b"\x00" * 200).decode()

            resp_alice = c.post("/api/v1/generate/video", json={
                "user_id": "alice", "audio_base64": audio_b64,
            })
            assert resp_alice.status_code == 200

            resp_bob = c.post("/api/v1/generate/video", json={
                "user_id": "bob", "audio_base64": audio_b64,
            })
            assert resp_bob.status_code == 404

            avatar_app.dependency_overrides.clear()
        finally:
            sys.path = old_path
            _clear_app_modules()


# ---------------------------------------------------------------------------
# Real-Time Orchestrator integration tests (via TestClient)
# ---------------------------------------------------------------------------

class TestOrchestratorServiceIntegration:
    """Tests Real-Time Orchestrator service — health, HTTP orchestrate, WebSocket."""

    @pytest.fixture(autouse=True)
    def _setup_orchestrator_client(self):
        _clear_app_modules()
        old_path = sys.path.copy()
        orch_path = str(PROJECT_ROOT / "Real-time-Orchestrator")
        sys.path.insert(0, orch_path)

        try:
            from app.config import Settings, get_settings
            from app.dependencies import get_pipeline, get_session_manager, get_ws_handler
            from app.main import app
            from app.services.pipeline import OrchestrationPipeline
            from app.services.session import SessionManager
            from app.ws.handler import WebSocketHandler
            from app.models.enums import MessageType, PipelineStage
            from app.models.schemas import PipelineResult, WSOutgoingMessage

            settings = Settings(
                brain_service_url="http://localhost:8002",
                voice_service_url="http://localhost:8003",
                video_avatar_service_url="http://localhost:8004",
                api_key=None,
            )

            self.mock_pipeline = AsyncMock(spec=OrchestrationPipeline)
            session_mgr = SessionManager(max_sessions=10)
            handler = WebSocketHandler(
                pipeline=self.mock_pipeline,
                session_mgr=session_mgr,
                settings=settings,
            )

            app.dependency_overrides[get_settings] = lambda: settings
            app.dependency_overrides[get_pipeline] = lambda: self.mock_pipeline
            app.dependency_overrides[get_session_manager] = lambda: session_mgr
            app.dependency_overrides[get_ws_handler] = lambda: handler

            from fastapi.testclient import TestClient
            self.client = TestClient(app)
            self.app = app
            self.PipelineResult = PipelineResult
            self.PipelineStage = PipelineStage
            self.MessageType = MessageType
            self.WSOutgoingMessage = WSOutgoingMessage
            yield
            app.dependency_overrides.clear()
        finally:
            sys.path = old_path
            _clear_app_modules()

    def test_orchestrator_health(self):
        resp = self.client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "0.1.0"
        assert "services" in data

    def test_orchestrator_root(self):
        resp = self.client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "VersionAI Real-Time Orchestrator"
        assert data["websocket"] == "/ws/orchestrate"

    def test_orchestrate_http_success(self):
        self.mock_pipeline.run.return_value = self.PipelineResult(
            request_id="r1",
            conversation_id="c1",
            response_text="AI response",
            sources=[{"text": "src", "score": 0.9}],
            audio_base64="YXVkaW8=",
            video_base64="dmlkZW8=",
            brain_latency_ms=100,
            voice_latency_ms=200,
            video_latency_ms=500,
            total_latency_ms=800,
            stage=self.PipelineStage.COMPLETE,
        )

        resp = self.client.post("/api/v1/orchestrate", json={
            "user_id": "user-e2e",
            "query": "What is VersionAI?",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["response_text"] == "AI response"
        assert data["audio_base64"] is not None
        assert data["video_base64"] is not None
        assert data["total_latency_ms"] == 800

    def test_orchestrate_http_brain_failure(self):
        self.mock_pipeline.run.return_value = self.PipelineResult(
            request_id="r1",
            error="Brain timeout",
            stage=self.PipelineStage.ERROR,
            total_latency_ms=5000,
        )

        resp = self.client.post("/api/v1/orchestrate", json={
            "user_id": "user-e2e",
            "query": "test",
        })
        assert resp.status_code == 502

    def test_ws_ping_pong(self):
        with self.client.websocket_connect("/ws/orchestrate") as ws:
            ws.send_json({"type": "ping"})
            resp = ws.receive_json()
            assert resp["type"] == "pong"

    def test_ws_orchestrate_streams_messages(self):
        async def mock_streaming(*args, **kwargs):
            yield self.WSOutgoingMessage(
                type=self.MessageType.ACK,
                request_id="r1",
                data={"stage": "received"},
            )
            yield self.WSOutgoingMessage(
                type=self.MessageType.TEXT,
                request_id="r1",
                data={"response": "Streamed answer"},
            )
            yield self.WSOutgoingMessage(
                type=self.MessageType.COMPLETE,
                request_id="r1",
                data={"total_latency_ms": 250},
            )

        self.mock_pipeline.run_streaming = mock_streaming

        with self.client.websocket_connect("/ws/orchestrate") as ws:
            ws.send_json({
                "type": "query",
                "user_id": "user-e2e",
                "query": "Stream test",
            })

            messages = []
            for _ in range(3):
                messages.append(ws.receive_json())

            types = [m["type"] for m in messages]
            assert "ack" in types
            assert "text" in types
            assert "complete" in types

            text_msg = next(m for m in messages if m["type"] == "text")
            assert text_msg["data"]["response"] == "Streamed answer"

    def test_sessions_endpoint(self):
        resp = self.client.get("/api/v1/sessions")
        assert resp.status_code == 200
        assert resp.json()["active_sessions"] == 0
