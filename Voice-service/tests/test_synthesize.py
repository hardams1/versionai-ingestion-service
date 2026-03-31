"""Tests for audio synthesis endpoints — the core profile-based audio generation flow."""

from __future__ import annotations

import struct

from fastapi.testclient import TestClient


def _create_profile(client: TestClient, user_id: str = "user-1", voice_id: str = "alloy") -> None:
    resp = client.post("/api/v1/profiles", json={
        "user_id": user_id,
        "voice_id": voice_id,
        "provider": "mock",
    })
    assert resp.status_code == 201


def _is_valid_wav(data: bytes) -> bool:
    """Check that data starts with a valid RIFF/WAVE header."""
    if len(data) < 44:
        return False
    return data[:4] == b"RIFF" and data[8:12] == b"WAVE"


# ---------------------------------------------------------------------------
# POST /api/v1/synthesize  (preview / validation — no audio generated)
# ---------------------------------------------------------------------------

class TestSynthesizePreview:

    def test_preview_resolves_profile(self, client: TestClient):
        _create_profile(client, "user-a", "echo")
        resp = client.post("/api/v1/synthesize", json={
            "text": "Hello world",
            "user_id": "user-a",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == "user-a"
        assert body["voice_id"] == "echo"
        assert body["status"] == "pending"
        assert body["tts_provider"] == "mock"
        assert body["text_length"] == 11
        assert body["duration_ms"] == 0.0

    def test_preview_no_profile_returns_404(self, client: TestClient):
        resp = client.post("/api/v1/synthesize", json={
            "text": "Hello",
            "user_id": "no-such-user",
        })
        assert resp.status_code == 404
        assert resp.json()["code"] == "VOICE_PROFILE_NOT_FOUND"

    def test_preview_text_too_long(self, client: TestClient):
        _create_profile(client, "user-b")
        resp = client.post("/api/v1/synthesize", json={
            "text": "x" * 5000,
            "user_id": "user-b",
        })
        assert resp.status_code == 422

    def test_preview_empty_text_rejected(self, client: TestClient):
        _create_profile(client, "user-c")
        resp = client.post("/api/v1/synthesize", json={
            "text": "",
            "user_id": "user-c",
        })
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/synthesize/audio  (actual audio generation)
# ---------------------------------------------------------------------------

class TestSynthesizeAudio:

    def test_generate_audio_returns_wav_bytes(self, client: TestClient):
        """Core test: create profile → synthesize → get valid audio back."""
        _create_profile(client, "user-1", "nova")
        resp = client.post("/api/v1/synthesize/audio", json={
            "text": "This is a test of voice synthesis.",
            "user_id": "user-1",
            "audio_format": "wav",
        })
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "audio/wav"
        assert resp.headers["x-voice-id"] == "nova"
        assert resp.headers["x-user-id"] == "user-1"
        assert _is_valid_wav(resp.content)
        assert len(resp.content) > 44  # more than just the header

    def test_audio_without_profile_returns_404(self, client: TestClient):
        resp = client.post("/api/v1/synthesize/audio", json={
            "text": "Hello",
            "user_id": "ghost-user",
        })
        assert resp.status_code == 404
        assert resp.json()["code"] == "VOICE_PROFILE_NOT_FOUND"

    def test_audio_text_too_long(self, client: TestClient):
        _create_profile(client, "user-tl")
        resp = client.post("/api/v1/synthesize/audio", json={
            "text": "a" * 5000,
            "user_id": "user-tl",
        })
        assert resp.status_code == 422

    def test_audio_default_format_is_mp3(self, client: TestClient):
        _create_profile(client, "user-fmt")
        resp = client.post("/api/v1/synthesize/audio", json={
            "text": "Test default format",
            "user_id": "user-fmt",
        })
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "audio/mpeg"

    def test_audio_content_length_header(self, client: TestClient):
        _create_profile(client, "user-cl")
        resp = client.post("/api/v1/synthesize/audio", json={
            "text": "Length check",
            "user_id": "user-cl",
        })
        assert resp.status_code == 200
        assert "content-length" in resp.headers
        assert int(resp.headers["content-length"]) == len(resp.content)

    def test_audio_duration_scales_with_text_length(self, client: TestClient):
        """Longer text should produce more audio data (MockTTS uses text length for duration)."""
        _create_profile(client, "user-dur")
        short = client.post("/api/v1/synthesize/audio", json={
            "text": "Hi",
            "user_id": "user-dur",
        })
        long = client.post("/api/v1/synthesize/audio", json={
            "text": "This is a much longer piece of text that should generate significantly more audio data than just a greeting.",
            "user_id": "user-dur",
        })
        assert len(long.content) > len(short.content)

    def test_different_users_get_different_voices(self, client: TestClient):
        """Each user's audio must be generated with their own voice profile."""
        _create_profile(client, "alice", "alloy")
        _create_profile(client, "bob", "shimmer")

        resp_a = client.post("/api/v1/synthesize/audio", json={
            "text": "Same text",
            "user_id": "alice",
        })
        resp_b = client.post("/api/v1/synthesize/audio", json={
            "text": "Same text",
            "user_id": "bob",
        })

        assert resp_a.headers["x-voice-id"] == "alloy"
        assert resp_b.headers["x-voice-id"] == "shimmer"

    def test_streaming_returns_chunked_audio(self, client: TestClient):
        _create_profile(client, "user-stream", "fable")
        resp = client.post("/api/v1/synthesize/audio", json={
            "text": "Streaming test content for the voice service",
            "user_id": "user-stream",
            "stream": True,
        })
        assert resp.status_code == 200
        assert resp.headers["x-voice-id"] == "fable"
        assert len(resp.content) > 0


# ---------------------------------------------------------------------------
# End-to-end: profile lifecycle + synthesis
# ---------------------------------------------------------------------------

class TestEndToEnd:

    def test_full_lifecycle(self, client: TestClient):
        """Create profile → synthesize → update profile → synthesize again → delete → fail."""
        # 1. Create profile
        resp = client.post("/api/v1/profiles", json={
            "user_id": "e2e-user",
            "voice_id": "alloy",
            "provider": "mock",
            "display_name": "E2E Test User",
        })
        assert resp.status_code == 201

        # 2. Synthesize audio with that profile
        resp = client.post("/api/v1/synthesize/audio", json={
            "text": "First synthesis with alloy voice",
            "user_id": "e2e-user",
        })
        assert resp.status_code == 200
        assert resp.headers["x-voice-id"] == "alloy"
        assert _is_valid_wav(resp.content)

        # 3. Update voice profile to a different voice
        resp = client.post("/api/v1/profiles", json={
            "user_id": "e2e-user",
            "voice_id": "shimmer",
            "provider": "mock",
        })
        assert resp.status_code == 201

        # 4. Synthesize again — should now use the updated voice
        resp = client.post("/api/v1/synthesize/audio", json={
            "text": "Second synthesis with shimmer voice",
            "user_id": "e2e-user",
        })
        assert resp.status_code == 200
        assert resp.headers["x-voice-id"] == "shimmer"

        # 5. Delete the profile
        resp = client.delete("/api/v1/profiles/e2e-user")
        assert resp.status_code == 204

        # 6. Synthesis should now fail with 404
        resp = client.post("/api/v1/synthesize/audio", json={
            "text": "This should fail",
            "user_id": "e2e-user",
        })
        assert resp.status_code == 404
        assert resp.json()["code"] == "VOICE_PROFILE_NOT_FOUND"

    def test_never_generates_generic_voice_for_unknown_user(self, client: TestClient):
        """System requirement: NEVER generate generic voices for known users.
        If no profile exists, the service must reject — not fall back to a default."""
        resp = client.post("/api/v1/synthesize/audio", json={
            "text": "Hello from unknown",
            "user_id": "completely-unknown-user",
        })
        assert resp.status_code == 404
        assert "VOICE_PROFILE_NOT_FOUND" in resp.json()["code"]
