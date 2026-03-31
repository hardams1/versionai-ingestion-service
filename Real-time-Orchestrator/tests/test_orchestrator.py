"""
Unit tests for the Real-Time Orchestrator service.

Verifies:
1. Service health endpoint returns status info
2. HTTP orchestrate endpoint runs the full pipeline
3. WebSocket handler streams progressive messages
4. Pipeline handles partial failures gracefully (voice/video down)
5. Session manager tracks concurrent connections
6. Service clients surface errors as typed exceptions
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("BRAIN_SERVICE_URL", "http://localhost:8002")
os.environ.setdefault("VOICE_SERVICE_URL", "http://localhost:8003")
os.environ.setdefault("VIDEO_AVATAR_SERVICE_URL", "http://localhost:8004")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


from app.config import Settings
from app.models.enums import MessageType, PipelineStage, SessionState
from app.models.schemas import (
    OrchestrateRequest,
    PipelineResult,
    WSIncomingMessage,
    WSOutgoingMessage,
)
from app.services.brain_client import BrainClient
from app.services.pipeline import OrchestrationPipeline
from app.services.session import Session, SessionManager
from app.services.video_client import VideoClient
from app.services.voice_client import VoiceClient
from app.utils.exceptions import (
    BrainServiceError,
    OrchestratorError,
    SessionLimitError,
    VideoServiceError,
    VoiceServiceError,
)


# ---------------------------------------------------------------------------
# Session Manager
# ---------------------------------------------------------------------------

class TestSessionManager:
    def test_create_and_remove(self):
        mgr = SessionManager(max_sessions=5)
        assert mgr.active_count == 0

        s = mgr.create("s1", "user-a")
        assert mgr.active_count == 1
        assert s.session_id == "s1"
        assert s.user_id == "user-a"
        assert s.state == SessionState.CONNECTED

        mgr.remove("s1")
        assert mgr.active_count == 0

    def test_capacity_check(self):
        mgr = SessionManager(max_sessions=2)
        assert mgr.can_accept() is True

        mgr.create("s1")
        mgr.create("s2")
        assert mgr.can_accept() is False

        mgr.remove("s1")
        assert mgr.can_accept() is True

    def test_get_returns_none_for_unknown(self):
        mgr = SessionManager()
        assert mgr.get("nonexistent") is None


# ---------------------------------------------------------------------------
# Pipeline (with mocked service clients)
# ---------------------------------------------------------------------------

class TestOrchestrationPipeline:
    def _make_pipeline(self):
        brain = AsyncMock(spec=BrainClient)
        voice = AsyncMock(spec=VoiceClient)
        video = AsyncMock(spec=VideoClient)
        return OrchestrationPipeline(brain, voice, video), brain, voice, video

    @pytest.mark.asyncio
    async def test_full_pipeline_success(self):
        pipeline, brain, voice, video = self._make_pipeline()

        brain.chat.return_value = {
            "response": "Hello world",
            "conversation_id": "conv-1",
            "sources": [{"text": "doc1", "score": 0.9}],
            "model_used": "gpt-4o",
            "_brain_latency_ms": 150.0,
        }
        voice.synthesize_b64.return_value = ("YXVkaW8=", b"audio", 200.0)
        video.generate_b64.return_value = ("dmlkZW8=", 500.0)

        result = await pipeline.run(
            user_id="user-1",
            query="What is VersionAI?",
        )

        assert result.response_text == "Hello world"
        assert result.conversation_id == "conv-1"
        assert result.audio_base64 == "YXVkaW8="
        assert result.video_base64 == "dmlkZW8="
        assert result.stage == PipelineStage.COMPLETE
        assert result.total_latency_ms > 0

    @pytest.mark.asyncio
    async def test_brain_failure_stops_pipeline(self):
        pipeline, brain, voice, video = self._make_pipeline()
        brain.chat.side_effect = BrainServiceError("timeout")

        result = await pipeline.run(user_id="u", query="test")

        assert result.stage == PipelineStage.ERROR
        assert "timeout" in result.error
        voice.synthesize_b64.assert_not_awaited()
        video.generate_b64.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_voice_failure_non_fatal(self):
        pipeline, brain, voice, video = self._make_pipeline()
        brain.chat.return_value = {
            "response": "Hello",
            "conversation_id": "c1",
            "sources": [],
            "model_used": "test",
            "_brain_latency_ms": 10,
        }
        voice.synthesize_b64.side_effect = VoiceServiceError("down")

        result = await pipeline.run(user_id="u", query="test")

        assert result.stage == PipelineStage.COMPLETE
        assert result.response_text == "Hello"
        assert result.audio_base64 is None
        assert result.video_base64 is None

    @pytest.mark.asyncio
    async def test_video_failure_non_fatal(self):
        pipeline, brain, voice, video = self._make_pipeline()
        brain.chat.return_value = {
            "response": "Hello",
            "conversation_id": "c1",
            "sources": [],
            "model_used": "test",
            "_brain_latency_ms": 10,
        }
        voice.synthesize_b64.return_value = ("YXVkaW8=", b"audio", 100.0)
        video.generate_b64.side_effect = VideoServiceError("renderer error")

        result = await pipeline.run(user_id="u", query="test")

        assert result.stage == PipelineStage.COMPLETE
        assert result.audio_base64 == "YXVkaW8="
        assert result.video_base64 is None

    @pytest.mark.asyncio
    async def test_skip_audio_and_video(self):
        pipeline, brain, voice, video = self._make_pipeline()
        brain.chat.return_value = {
            "response": "Text only",
            "conversation_id": "c1",
            "sources": [],
            "model_used": "test",
            "_brain_latency_ms": 5,
        }

        result = await pipeline.run(
            user_id="u", query="test",
            include_audio=False, include_video=False,
        )

        assert result.response_text == "Text only"
        assert result.audio_base64 is None
        assert result.video_base64 is None
        voice.synthesize_b64.assert_not_awaited()
        video.generate_b64.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_streaming_yields_progressive_messages(self):
        pipeline, brain, voice, video = self._make_pipeline()
        brain.chat.return_value = {
            "response": "Streamed",
            "conversation_id": "c1",
            "sources": [],
            "model_used": "test",
            "_brain_latency_ms": 10,
        }
        voice.synthesize_b64.return_value = ("YXVkaW8=", b"audio", 50.0)
        video.generate_b64.return_value = ("dmlkZW8=", 100.0)

        messages = []
        async for msg in pipeline.run_streaming(
            user_id="u", query="test", request_id="r1",
        ):
            messages.append(msg)

        types = [m.type for m in messages]
        assert MessageType.ACK in types
        assert MessageType.TEXT in types
        assert MessageType.AUDIO in types
        assert MessageType.VIDEO in types
        assert MessageType.COMPLETE in types

        text_msg = next(m for m in messages if m.type == MessageType.TEXT)
        assert text_msg.data["response"] == "Streamed"


# ---------------------------------------------------------------------------
# FastAPI TestClient — HTTP endpoints
# ---------------------------------------------------------------------------

class TestHTTPEndpoints:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from app.main import app
        from app.dependencies import get_pipeline, get_session_manager

        self.mock_pipeline = AsyncMock(spec=OrchestrationPipeline)
        self.mock_session_mgr = SessionManager(max_sessions=10)

        app.dependency_overrides[get_pipeline] = lambda: self.mock_pipeline
        app.dependency_overrides[get_session_manager] = lambda: self.mock_session_mgr

        from fastapi.testclient import TestClient
        self.client = TestClient(app)
        self.app = app
        yield
        app.dependency_overrides.clear()

    def test_root_endpoint(self):
        resp = self.client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "VersionAI Real-Time Orchestrator"
        assert "websocket" in data

    def test_health_endpoint(self):
        resp = self.client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "0.1.0"
        assert "services" in data

    def test_sessions_endpoint(self):
        resp = self.client.get("/api/v1/sessions")
        assert resp.status_code == 200
        assert resp.json()["active_sessions"] == 0

    def test_orchestrate_success(self):
        self.mock_pipeline.run.return_value = PipelineResult(
            request_id="r1",
            conversation_id="c1",
            response_text="AI answer",
            sources=[{"text": "source", "score": 0.95}],
            audio_base64="YXVkaW8=",
            video_base64="dmlkZW8=",
            brain_latency_ms=100,
            voice_latency_ms=200,
            video_latency_ms=500,
            total_latency_ms=800,
            stage=PipelineStage.COMPLETE,
        )

        resp = self.client.post("/api/v1/orchestrate", json={
            "user_id": "user-1",
            "query": "What is VersionAI?",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["response_text"] == "AI answer"
        assert data["audio_base64"] == "YXVkaW8="
        assert data["video_base64"] == "dmlkZW8="
        assert "brain" in data["stages"]

    def test_orchestrate_brain_error(self):
        self.mock_pipeline.run.return_value = PipelineResult(
            request_id="r1",
            error="Brain service timeout",
            stage=PipelineStage.ERROR,
            total_latency_ms=5000,
        )

        resp = self.client.post("/api/v1/orchestrate", json={
            "user_id": "user-1",
            "query": "test",
        })
        assert resp.status_code == 502


# ---------------------------------------------------------------------------
# WebSocket tests
# ---------------------------------------------------------------------------

class TestWebSocket:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from app.main import app
        from app.dependencies import get_pipeline, get_ws_handler
        from app.services.pipeline import OrchestrationPipeline
        from app.ws.handler import WebSocketHandler

        self.mock_pipeline = AsyncMock(spec=OrchestrationPipeline)
        mock_session_mgr = SessionManager(max_sessions=10)

        settings = Settings(
            brain_service_url="http://localhost:8002",
            voice_service_url="http://localhost:8003",
            video_avatar_service_url="http://localhost:8004",
        )

        handler = WebSocketHandler(
            pipeline=self.mock_pipeline,
            session_mgr=mock_session_mgr,
            settings=settings,
        )

        app.dependency_overrides[get_ws_handler] = lambda: handler

        from fastapi.testclient import TestClient
        self.client = TestClient(app)
        self.app = app
        yield
        app.dependency_overrides.clear()

    def test_ws_ping_pong(self):
        with self.client.websocket_connect("/ws/orchestrate") as ws:
            ws.send_json({"type": "ping"})
            resp = ws.receive_json()
            assert resp["type"] == "pong"

    def test_ws_query_streams_messages(self):
        async def mock_streaming(*args, **kwargs):
            yield WSOutgoingMessage(
                type=MessageType.ACK,
                request_id="r1",
                data={"stage": "received"},
            )
            yield WSOutgoingMessage(
                type=MessageType.TEXT,
                request_id="r1",
                data={"response": "Hello"},
            )
            yield WSOutgoingMessage(
                type=MessageType.COMPLETE,
                request_id="r1",
                data={"total_latency_ms": 100},
            )

        self.mock_pipeline.run_streaming = mock_streaming

        with self.client.websocket_connect("/ws/orchestrate") as ws:
            ws.send_json({
                "type": "query",
                "user_id": "user-1",
                "query": "Hello",
            })

            messages = []
            for _ in range(3):
                messages.append(ws.receive_json())

            types = [m["type"] for m in messages]
            assert "ack" in types
            assert "text" in types
            assert "complete" in types

    def test_ws_missing_user_id(self):
        with self.client.websocket_connect("/ws/orchestrate") as ws:
            ws.send_json({"type": "query", "query": "Hello"})
            resp = ws.receive_json()
            assert resp["type"] == "error"

    def test_ws_unknown_message_type(self):
        with self.client.websocket_connect("/ws/orchestrate") as ws:
            ws.send_json({"type": "unknown_type"})
            resp = ws.receive_json()
            assert resp["type"] == "error"
            assert "Unknown" in resp["data"]["detail"]


# ---------------------------------------------------------------------------
# Exception classes
# ---------------------------------------------------------------------------

class TestExceptions:
    def test_brain_error(self):
        e = BrainServiceError("timeout")
        assert e.status_code == 502
        assert e.code == "BRAIN_SERVICE_ERROR"

    def test_voice_error(self):
        e = VoiceServiceError("down")
        assert e.status_code == 502

    def test_video_error(self):
        e = VideoServiceError("failed")
        assert e.status_code == 502

    def test_session_limit(self):
        e = SessionLimitError(100)
        assert e.status_code == 503
        assert "100" in e.detail
