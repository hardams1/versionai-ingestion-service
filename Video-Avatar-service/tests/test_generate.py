"""Tests for video generation — the core audio-to-video flow with validated avatars."""

from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from tests.conftest import b64_image, create_test_jpeg

SAMPLE_AUDIO = b"\x00" * 4000


def _b64_audio(data: bytes = SAMPLE_AUDIO) -> str:
    return base64.b64encode(data).decode()


def _create_avatar(
    client: TestClient,
    user_id: str = "user-1",
    avatar_id: str = "avatar-1",
) -> None:
    resp = client.post("/api/v1/avatars", json={
        "user_id": user_id,
        "avatar_id": avatar_id,
        "source_image_base64": b64_image(create_test_jpeg(256, 256)),
        "provider": "mock",
    })
    assert resp.status_code == 201, resp.json()


def _is_valid_mp4(data: bytes) -> bool:
    if len(data) < 12:
        return False
    return data[4:8] == b"ftyp"


# ---------------------------------------------------------------------------
# POST /api/v1/generate  (preview / validation)
# ---------------------------------------------------------------------------

class TestGeneratePreview:

    def test_preview_resolves_avatar(self, client: TestClient):
        _create_avatar(client, "user-a", "avatar-a")
        resp = client.post("/api/v1/generate", json={
            "user_id": "user-a",
            "audio_base64": _b64_audio(),
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == "user-a"
        assert body["avatar_id"] == "avatar-a"
        assert body["status"] == "pending"
        assert body["renderer_provider"] == "mock"
        assert body["duration_ms"] == 0.0

    def test_preview_no_avatar_returns_404(self, client: TestClient):
        resp = client.post("/api/v1/generate", json={
            "user_id": "no-such-user",
            "audio_base64": _b64_audio(),
        })
        assert resp.status_code == 404
        assert resp.json()["code"] == "AVATAR_PROFILE_NOT_FOUND"

    def test_preview_no_audio_returns_422(self, client: TestClient):
        _create_avatar(client, "user-b")
        resp = client.post("/api/v1/generate", json={
            "user_id": "user-b",
        })
        assert resp.status_code == 422

    def test_preview_invalid_base64_returns_422(self, client: TestClient):
        _create_avatar(client, "user-c")
        resp = client.post("/api/v1/generate", json={
            "user_id": "user-c",
            "audio_base64": "not-valid-base64!!!",
        })
        assert resp.status_code == 422

    def test_preview_audio_too_small(self, client: TestClient):
        _create_avatar(client, "user-d")
        resp = client.post("/api/v1/generate", json={
            "user_id": "user-d",
            "audio_base64": base64.b64encode(b"\x00" * 10).decode(),
        })
        assert resp.status_code == 422
        assert resp.json()["code"] == "INVALID_AUDIO"


# ---------------------------------------------------------------------------
# POST /api/v1/generate/video  (actual video generation)
# ---------------------------------------------------------------------------

class TestGenerateVideo:

    def test_generate_returns_mp4_bytes(self, client: TestClient):
        _create_avatar(client, "user-1", "avatar-1")
        resp = client.post("/api/v1/generate/video", json={
            "user_id": "user-1",
            "audio_base64": _b64_audio(),
            "video_format": "mp4",
        })
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "video/mp4"
        assert resp.headers["x-avatar-id"] == "avatar-1"
        assert resp.headers["x-user-id"] == "user-1"
        assert float(resp.headers["x-video-duration"]) > 0
        assert float(resp.headers["x-render-time-ms"]) >= 0
        assert _is_valid_mp4(resp.content)
        assert len(resp.content) > 20

    def test_video_without_avatar_returns_404(self, client: TestClient):
        resp = client.post("/api/v1/generate/video", json={
            "user_id": "ghost-user",
            "audio_base64": _b64_audio(),
        })
        assert resp.status_code == 404
        assert resp.json()["code"] == "AVATAR_PROFILE_NOT_FOUND"

    def test_video_content_length_matches(self, client: TestClient):
        _create_avatar(client, "user-cl")
        resp = client.post("/api/v1/generate/video", json={
            "user_id": "user-cl",
            "audio_base64": _b64_audio(),
        })
        assert resp.status_code == 200
        assert "content-length" in resp.headers
        assert int(resp.headers["content-length"]) == len(resp.content)

    def test_video_duration_scales_with_audio(self, client: TestClient):
        _create_avatar(client, "user-dur")
        short_audio = _b64_audio(b"\x00" * 1000)
        long_audio = _b64_audio(b"\x00" * 100_000)

        short = client.post("/api/v1/generate/video", json={
            "user_id": "user-dur",
            "audio_base64": short_audio,
        })
        long = client.post("/api/v1/generate/video", json={
            "user_id": "user-dur",
            "audio_base64": long_audio,
        })
        assert float(long.headers["x-video-duration"]) > float(short.headers["x-video-duration"])

    def test_default_format_is_mp4(self, client: TestClient):
        _create_avatar(client, "user-fmt")
        resp = client.post("/api/v1/generate/video", json={
            "user_id": "user-fmt",
            "audio_base64": _b64_audio(),
        })
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "video/mp4"

    def test_different_users_get_different_avatars(self, client: TestClient):
        _create_avatar(client, "alice", "alice-face")
        _create_avatar(client, "bob", "bob-face")

        resp_a = client.post("/api/v1/generate/video", json={
            "user_id": "alice",
            "audio_base64": _b64_audio(),
        })
        resp_b = client.post("/api/v1/generate/video", json={
            "user_id": "bob",
            "audio_base64": _b64_audio(),
        })

        assert resp_a.headers["x-avatar-id"] == "alice-face"
        assert resp_b.headers["x-avatar-id"] == "bob-face"

    def test_deterministic_output(self, client: TestClient):
        _create_avatar(client, "user-det", "det-avatar")
        payload = {
            "user_id": "user-det",
            "audio_base64": _b64_audio(),
            "video_format": "mp4",
        }
        r1 = client.post("/api/v1/generate/video", json=payload)
        r2 = client.post("/api/v1/generate/video", json=payload)
        assert r1.content == r2.content

    def test_idle_mode_generates_video(self, client: TestClient):
        _create_avatar(client, "user-idle", "idle-avatar")
        resp = client.post("/api/v1/generate/video", json={
            "user_id": "user-idle",
            "audio_base64": _b64_audio(),
            "idle_mode": True,
        })
        assert resp.status_code == 200
        assert _is_valid_mp4(resp.content)


# ---------------------------------------------------------------------------
# End-to-end: avatar lifecycle + video generation
# ---------------------------------------------------------------------------

class TestEndToEnd:

    def test_full_lifecycle(self, client: TestClient):
        """Create avatar with real image → generate video → update → generate → delete → fail."""
        img_v1 = create_test_jpeg(256, 256, (200, 100, 50))
        img_v2 = create_test_jpeg(300, 300, (50, 100, 200))

        resp = client.post("/api/v1/avatars", json={
            "user_id": "e2e-user",
            "avatar_id": "face-v1",
            "source_image_base64": b64_image(img_v1),
            "provider": "mock",
            "display_name": "E2E Test Avatar",
        })
        assert resp.status_code == 201
        assert resp.json()["image_width"] == 256
        assert resp.json()["image_source"] == "upload"

        resp = client.post("/api/v1/generate/video", json={
            "user_id": "e2e-user",
            "audio_base64": _b64_audio(),
        })
        assert resp.status_code == 200
        assert resp.headers["x-avatar-id"] == "face-v1"
        assert _is_valid_mp4(resp.content)

        resp = client.post("/api/v1/avatars", json={
            "user_id": "e2e-user",
            "avatar_id": "face-v2",
            "source_image_base64": b64_image(img_v2),
            "provider": "mock",
        })
        assert resp.status_code == 201
        assert resp.json()["image_width"] == 300

        resp = client.post("/api/v1/generate/video", json={
            "user_id": "e2e-user",
            "audio_base64": _b64_audio(),
        })
        assert resp.status_code == 200
        assert resp.headers["x-avatar-id"] == "face-v2"

        resp = client.delete("/api/v1/avatars/e2e-user")
        assert resp.status_code == 204

        resp = client.post("/api/v1/generate/video", json={
            "user_id": "e2e-user",
            "audio_base64": _b64_audio(),
        })
        assert resp.status_code == 404
        assert resp.json()["code"] == "AVATAR_PROFILE_NOT_FOUND"

    def test_never_generates_generic_face_for_unknown_user(self, client: TestClient):
        resp = client.post("/api/v1/generate/video", json={
            "user_id": "completely-unknown-user",
            "audio_base64": _b64_audio(),
        })
        assert resp.status_code == 404
        assert "AVATAR_PROFILE_NOT_FOUND" in resp.json()["code"]

    def test_video_only_works_with_validated_photorealistic_avatar(self, client: TestClient):
        """Cannot bypass image validation — you MUST provide a valid face image."""
        resp = client.post("/api/v1/avatars", json={
            "user_id": "bypass-user",
            "avatar_id": "bypass-avatar",
            "source_image_base64": base64.b64encode(b"not an image " * 50).decode(),
        })
        assert resp.status_code == 422

        resp = client.post("/api/v1/generate/video", json={
            "user_id": "bypass-user",
            "audio_base64": _b64_audio(),
        })
        assert resp.status_code == 404
