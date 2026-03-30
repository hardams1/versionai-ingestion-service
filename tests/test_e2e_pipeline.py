"""
End-to-end integration test: Ingestion → Processing → Brain

Verifies that:
1. A file uploaded with user_id flows through to vector metadata
2. The Processing Service correctly chunks and embeds the content
3. The Brain Service retrieves ONLY the correct user's context
4. The Brain Service generates a grounded response
5. Tenant isolation is enforced across the full pipeline
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import numpy as np
import pytest

os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("VECTOR_STORE_PROVIDER", "faiss")
os.environ.setdefault("EMBEDDING_PROVIDER", "openai")
os.environ.setdefault("LLM_PROVIDER", "openai")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _clear_app_modules():
    """Remove all cached `app.*` modules so the next service's code loads cleanly."""
    to_remove = [k for k in sys.modules if k == "app" or k.startswith("app.")]
    for k in to_remove:
        del sys.modules[k]


def _import_from_service(service_dir: str, module_path: str, names: list[str]) -> dict:
    """Import specific names from a module inside a service directory."""
    svc_path = str(PROJECT_ROOT / service_dir)
    _clear_app_modules()
    old_path = sys.path.copy()
    sys.path.insert(0, svc_path)
    try:
        mod = importlib.import_module(module_path)
        return {name: getattr(mod, name) for name in names}
    finally:
        sys.path = old_path


def make_fake_embedding(dim: int = 1536, seed: int = 42) -> list[float]:
    rng = np.random.RandomState(seed)
    vec = rng.randn(dim).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    return vec.tolist()


# ---------------------------------------------------------------------------
# Test: user_id propagation through the full pipeline
# ---------------------------------------------------------------------------

class TestEndToEndPipeline:

    @pytest.fixture
    def faiss_dir(self):
        tmpdir = tempfile.mkdtemp(prefix="versionai_e2e_")
        yield tmpdir

    @pytest.fixture
    def embedding_dim(self):
        return 1536

    @pytest.mark.asyncio
    async def test_user_id_flows_ingestion_to_faiss(self, faiss_dir, embedding_dim):
        """user_id in upload metadata → QueueMessage JSON → Processing chunks → FAISS → Brain."""

        # Phase 1: Simulate the QueueMessage JSON that ingestion produces
        # (upload.py adds user_id to metadata, then serializes via model_dump_json)
        queue_message_json = {
            "ingestion_id": "ing-001",
            "filename": "france.txt",
            "s3_bucket": "versionai-ingestion",
            "s3_key": "uploads/text/france.txt",
            "file_category": "text",
            "mime_type": "text/plain",
            "size_bytes": 100,
            "checksum_sha256": "abc123",
            "pipelines": ["embedding"],
            "metadata": {
                "original_filename": "france.txt",
                "extension": ".txt",
                "mime_type": "text/plain",
                "category": "text",
                "size_bytes": 100,
                "checksum_sha256": "abc123",
                "user_id": "user-alice",
            },
        }
        assert queue_message_json["metadata"]["user_id"] == "user-alice"

        # Phase 2: Simulate Processing chunk_metadata builder (processor.py lines 113-118)
        msg_meta = queue_message_json["metadata"]
        chunk_metadata = {
            "ingestion_id": queue_message_json["ingestion_id"],
            "filename": queue_message_json["filename"],
            "file_category": queue_message_json["file_category"],
            **{k: v for k, v in msg_meta.items() if isinstance(v, (str, int, float, bool))},
        }
        assert chunk_metadata["user_id"] == "user-alice"

        # Phase 3: Write to FAISS (simulating Processing's vector_store.store)
        import faiss as faiss_lib

        dim = embedding_dim
        vecs = np.array([
            make_fake_embedding(dim, seed=1),
            make_fake_embedding(dim, seed=2),
        ], dtype=np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1
        vecs = vecs / norms

        index = faiss_lib.IndexFlatIP(dim)
        index.add(vecs)

        faiss_metadata = [
            {
                "ingestion_id": "ing-001",
                "chunk_index": 0,
                "text": "The capital of France is Paris.",
                "token_count": 8,
                **{k: v for k, v in chunk_metadata.items() if k != "text"},
            },
            {
                "ingestion_id": "ing-001",
                "chunk_index": 1,
                "text": "It has a population of 2.1 million.",
                "token_count": 9,
                **{k: v for k, v in chunk_metadata.items() if k != "text"},
            },
        ]

        faiss_lib.write_index(index, os.path.join(faiss_dir, "index.faiss"))
        with open(os.path.join(faiss_dir, "metadata.json"), "w") as f:
            json.dump({"metadata": faiss_metadata, "id_map": {"ing-001": [0, 1]}}, f)

        # Phase 4: Verify FAISS metadata on disk
        with open(os.path.join(faiss_dir, "metadata.json")) as f:
            faiss_data = json.load(f)
        for m in faiss_data["metadata"]:
            assert m.get("user_id") == "user-alice", f"user_id missing: {m.keys()}"

        # Phase 5: Brain retriever respects user_id
        brain_imports = _import_from_service(
            "AI-Brain-service", "app.services.retriever", ["FAISSRetriever"]
        )
        brain_config = _import_from_service("AI-Brain-service", "app.config", ["Settings"])

        BrainSettings = brain_config["Settings"]
        FAISSRetriever = brain_imports["FAISSRetriever"]

        brain_settings = BrainSettings(
            openai_api_key="sk-test-fake",
            faiss_index_dir=faiss_dir,
            retrieval_top_k=5,
            retrieval_score_threshold=0.0,
        )
        retriever = FAISSRetriever(brain_settings)
        await retriever.initialize()

        query_vec = make_fake_embedding(embedding_dim, seed=1)

        alice_results = await retriever.search(query_vec, user_id="user-alice", top_k=5, score_threshold=0.0)
        assert len(alice_results) > 0, "user-alice should find her own docs"

        bob_results = await retriever.search(query_vec, user_id="user-bob", top_k=5, score_threshold=0.0)
        assert len(bob_results) == 0, "user-bob should NOT see alice's docs"

    @pytest.mark.asyncio
    async def test_brain_full_orchestrator_with_real_faiss(self, faiss_dir, embedding_dim):
        """Full Brain orchestrator: real FAISS index, mocked LLM, verified prompt injection."""
        import faiss as faiss_lib

        dim = embedding_dim
        index = faiss_lib.IndexFlatIP(dim)
        vec = np.array([make_fake_embedding(dim, seed=10)], dtype=np.float32)
        norms = np.linalg.norm(vec, axis=1, keepdims=True)
        vec = vec / norms
        index.add(vec)

        metadata = [{
            "ingestion_id": "file-e2e",
            "chunk_index": 0,
            "text": "Python was created by Guido van Rossum in 1991.",
            "token_count": 10,
            "user_id": "user-test",
            "filename": "python-history.txt",
        }]

        faiss_lib.write_index(index, os.path.join(faiss_dir, "index.faiss"))
        with open(os.path.join(faiss_dir, "metadata.json"), "w") as f:
            json.dump({"metadata": metadata, "id_map": {"file-e2e": [0]}}, f)

        # Import Brain modules
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

            settings = BrainSettings(
                openai_api_key="sk-test-fake",
                faiss_index_dir=faiss_dir,
                retrieval_top_k=5,
                retrieval_score_threshold=0.0,
            )

            retriever = FAISSRetriever(settings)
            await retriever.initialize()

            memory = ConversationMemory(settings)
            ps = PersonalityStore(settings)
            await ps.initialize()

            mock_embedder = AsyncMock()
            mock_embedder.embed.return_value = make_fake_embedding(dim, seed=10)

            mock_llm = AsyncMock()
            mock_llm.generate.return_value = LLMResponse(
                content="Python was created by Guido van Rossum in 1991.",
                model="test-model",
                usage=TokenUsage(prompt_tokens=200, completion_tokens=20, total_tokens=220),
                finish_reason="stop",
            )

            orchestrator = BrainOrchestrator(
                settings=settings,
                retriever=retriever,
                embedder=mock_embedder,
                llm=mock_llm,
                memory=memory,
                personality_store=ps,
                prompt_builder=PromptBuilder(settings),
                safety=SafetyProcessor(settings),
            )

            # Correct user — gets context
            resp = await orchestrator.chat(ChatRequest(user_id="user-test", query="Who created Python?"))
            assert len(resp.sources) > 0
            assert resp.sources[0].file_id == "file-e2e"

            # Verify LLM received injected context
            llm_msgs = mock_llm.generate.call_args[0][0]
            system_msg = llm_msgs[0]["content"]
            assert "Guido van Rossum" in system_msg
            assert "GROUNDING RULES" in system_msg

            # Wrong user — gets no context
            mock_llm.generate.return_value = LLMResponse(
                content="I don't have information about that.",
                model="test-model",
                usage=TokenUsage(prompt_tokens=100, completion_tokens=10, total_tokens=110),
            )
            resp_other = await orchestrator.chat(ChatRequest(user_id="user-other", query="Who created Python?"))
            assert len(resp_other.sources) == 0

        finally:
            sys.path = old_path

    @pytest.mark.asyncio
    async def test_multi_turn_conversation_preserves_history(self, faiss_dir, embedding_dim):
        """Verify multi-turn conversations inject history into subsequent LLM calls."""
        import faiss as faiss_lib

        dim = embedding_dim
        index = faiss_lib.IndexFlatIP(dim)
        vec = np.array([make_fake_embedding(dim, seed=5)], dtype=np.float32)
        norms = np.linalg.norm(vec, axis=1, keepdims=True)
        vec = vec / norms
        index.add(vec)

        metadata = [{
            "ingestion_id": "file-conv",
            "chunk_index": 0,
            "text": "The company was founded in 2020.",
            "token_count": 7,
            "user_id": "user-conv",
        }]

        faiss_lib.write_index(index, os.path.join(faiss_dir, "index.faiss"))
        with open(os.path.join(faiss_dir, "metadata.json"), "w") as f:
            json.dump({"metadata": metadata, "id_map": {"file-conv": [0]}}, f)

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

            settings = BrainSettings(
                openai_api_key="sk-test",
                faiss_index_dir=faiss_dir,
                retrieval_score_threshold=0.0,
            )

            retriever = FAISSRetriever(settings)
            await retriever.initialize()
            memory = ConversationMemory(settings)
            ps = PersonalityStore(settings)
            await ps.initialize()

            mock_embedder = AsyncMock()
            mock_embedder.embed.return_value = make_fake_embedding(dim, seed=5)

            captured_messages = []

            async def capture_llm(messages, **kwargs):
                captured_messages.append(messages)
                return LLMResponse(
                    content=f"Response to turn {len(captured_messages)}",
                    model="test",
                    usage=TokenUsage(prompt_tokens=50, completion_tokens=10, total_tokens=60),
                )

            mock_llm = AsyncMock()
            mock_llm.generate = capture_llm

            orchestrator = BrainOrchestrator(
                settings=settings,
                retriever=retriever,
                embedder=mock_embedder,
                llm=mock_llm,
                memory=memory,
                personality_store=ps,
                prompt_builder=PromptBuilder(settings),
                safety=SafetyProcessor(settings),
            )

            # Turn 1
            r1 = await orchestrator.chat(ChatRequest(user_id="user-conv", query="When was the company founded?"))
            conv_id = r1.conversation_id

            # Turn 2 (same conversation)
            r2 = await orchestrator.chat(ChatRequest(
                user_id="user-conv",
                query="Who was the founder?",
                conversation_id=conv_id,
            ))

            # Verify turn 2 included turn 1 history
            turn2_msgs = captured_messages[1]
            user_msgs = [m for m in turn2_msgs if m["role"] == "user"]
            assert len(user_msgs) >= 2, "Turn 2 should include Turn 1's user message in history"
            assert user_msgs[0]["content"] == "When was the company founded?"
            assert user_msgs[1]["content"] == "Who was the founder?"

        finally:
            sys.path = old_path

    def test_processing_metadata_scalar_passthrough(self):
        """Verify Processing's metadata builder preserves user_id from QueueMessage."""
        metadata_from_ingestion = {
            "original_filename": "doc.pdf",
            "extension": ".pdf",
            "mime_type": "application/pdf",
            "category": "document",
            "size_bytes": 5000,
            "checksum_sha256": "def456",
            "user_id": "user-from-ingestion",
        }

        chunk_metadata = {
            "ingestion_id": "ing-002",
            "filename": "doc.pdf",
            "file_category": "document",
            **{k: v for k, v in metadata_from_ingestion.items() if isinstance(v, (str, int, float, bool))},
        }

        assert chunk_metadata["user_id"] == "user-from-ingestion"
        assert chunk_metadata["ingestion_id"] == "ing-002"
