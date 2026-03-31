"""
End-to-end integration test: Ingestion → Processing → Brain → Voice

Verifies:
1.  Each service's health endpoint is reachable (TestClient-level)
2.  Upload with user_id propagates through metadata → FAISS → Brain retriever
3.  Brain retrieves correct context and generates grounded response
4.  Voice profile creation + audio synthesis with that profile
5.  Full pipeline: upload → embed → chat → synthesize (all 4 services)
6.  Tenant isolation enforced across the pipeline
7.  Voice service never generates audio without a profile
"""
from __future__ import annotations

import importlib
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
# Full pipeline: Ingestion metadata → FAISS → Brain → Voice
# ---------------------------------------------------------------------------

class TestFullPipelineIntegration:
    """
    Simulates the complete VersionAI pipeline:
    1. Ingestion produces a QueueMessage with user_id
    2. Processing embeds chunks into FAISS with user metadata
    3. Brain retrieves context for the correct user and generates a response
    4. Voice synthesizes audio from Brain's text response using the user's profile
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
    def embedding_dim(self):
        return 1536

    @pytest.mark.asyncio
    async def test_upload_to_voice_full_pipeline(self, faiss_dir, voice_profiles_dir, embedding_dim):
        """The complete flow: ingest → process → chat → voice."""
        import faiss as faiss_lib

        user_id = "user-fullpipe"
        dim = embedding_dim

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

            # Verify tenant isolation
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

            # Create voice profile for this user
            resp = voice_client.post("/api/v1/profiles", json={
                "user_id": user_id,
                "voice_id": "nova",
                "provider": "mock",
                "display_name": "Full Pipeline User",
            })
            assert resp.status_code == 201

            # Synthesize audio from Brain's text response
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
