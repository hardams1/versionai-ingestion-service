"""Tests for avatar profile CRUD with photorealistic image validation."""

from __future__ import annotations

import base64
import io

from fastapi.testclient import TestClient
from PIL import Image

from tests.conftest import b64_image, create_test_jpeg, create_test_png


def _create_avatar(
    client: TestClient,
    user_id: str = "user-1",
    avatar_id: str = "avatar-1",
    image_bytes: bytes | None = None,
) -> dict:
    resp = client.post("/api/v1/avatars", json={
        "user_id": user_id,
        "avatar_id": avatar_id,
        "source_image_base64": b64_image(image_bytes),
        "provider": "mock",
    })
    assert resp.status_code == 201, resp.json()
    return resp.json()


# ---------------------------------------------------------------------------
# Image validation — photorealistic quality gates
# ---------------------------------------------------------------------------

class TestImageValidation:

    def test_valid_jpeg_accepted(self, client: TestClient):
        body = _create_avatar(client, "u1", "a1", create_test_jpeg(512, 512))
        assert body["image_format"] == "JPEG"
        assert body["image_width"] == 512
        assert body["image_height"] == 512

    def test_valid_png_accepted(self, client: TestClient):
        body = _create_avatar(client, "u2", "a2", create_test_png(300, 300))
        assert body["image_format"] == "PNG"
        assert body["image_width"] == 300
        assert body["image_height"] == 300

    def test_rejects_non_image_data(self, client: TestClient):
        fake_data = b"This is not an image at all " * 100
        resp = client.post("/api/v1/avatars", json={
            "user_id": "u-bad",
            "avatar_id": "a-bad",
            "source_image_base64": base64.b64encode(fake_data).decode(),
        })
        assert resp.status_code == 422
        assert resp.json()["code"] == "INVALID_IMAGE"

    def test_rejects_too_small_resolution(self, client: TestClient):
        tiny = create_test_jpeg(32, 32)
        resp = client.post("/api/v1/avatars", json={
            "user_id": "u-tiny",
            "avatar_id": "a-tiny",
            "source_image_base64": b64_image(tiny),
        })
        assert resp.status_code == 422
        assert resp.json()["code"] == "IMAGE_TOO_SMALL"

    def test_rejects_grayscale_image(self, client: TestClient):
        img = Image.new("L", (256, 256), 128)
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        gray_bytes = buf.getvalue()
        resp = client.post("/api/v1/avatars", json={
            "user_id": "u-gray",
            "avatar_id": "a-gray",
            "source_image_base64": b64_image(gray_bytes),
        })
        assert resp.status_code == 422
        assert resp.json()["code"] == "IMAGE_NOT_RGB"

    def test_rejects_extreme_aspect_ratio(self, client: TestClient):
        wide = create_test_jpeg(800, 100)
        resp = client.post("/api/v1/avatars", json={
            "user_id": "u-wide",
            "avatar_id": "a-wide",
            "source_image_base64": b64_image(wide),
        })
        assert resp.status_code == 422
        assert resp.json()["code"] == "IMAGE_ASPECT_RATIO"

    def test_rejects_too_small_file_size(self, client: TestClient):
        resp = client.post("/api/v1/avatars", json={
            "user_id": "u-mini",
            "avatar_id": "a-mini",
            "source_image_base64": base64.b64encode(b"\xff\xd8\xff" + b"\x00" * 50).decode(),
        })
        assert resp.status_code == 422
        assert resp.json()["code"] == "INVALID_IMAGE"

    def test_rejects_invalid_base64(self, client: TestClient):
        resp = client.post("/api/v1/avatars", json={
            "user_id": "u-b64",
            "avatar_id": "a-b64",
            "source_image_base64": "not-valid-base64!!!@@@",
        })
        assert resp.status_code == 422
        assert resp.json()["code"] == "INVALID_IMAGE"

    def test_rejects_gif_format(self, client: TestClient):
        img = Image.new("RGB", (256, 256), (100, 100, 100))
        buf = io.BytesIO()
        img.save(buf, format="GIF")
        gif_bytes = buf.getvalue()
        resp = client.post("/api/v1/avatars", json={
            "user_id": "u-gif",
            "avatar_id": "a-gif",
            "source_image_base64": b64_image(gif_bytes),
        })
        assert resp.status_code == 422
        assert resp.json()["code"] == "UNSUPPORTED_IMAGE_FORMAT"

    def test_rejects_bmp_format(self, client: TestClient):
        img = Image.new("RGB", (256, 256), (100, 100, 100))
        buf = io.BytesIO()
        img.save(buf, format="BMP")
        bmp_bytes = buf.getvalue()
        resp = client.post("/api/v1/avatars", json={
            "user_id": "u-bmp",
            "avatar_id": "a-bmp",
            "source_image_base64": b64_image(bmp_bytes),
        })
        assert resp.status_code == 422
        assert resp.json()["code"] == "UNSUPPORTED_IMAGE_FORMAT"


# ---------------------------------------------------------------------------
# Avatar profile CRUD
# ---------------------------------------------------------------------------

class TestCreateAvatar:

    def test_create_returns_201_with_image_metadata(self, client: TestClient):
        resp = client.post("/api/v1/avatars", json={
            "user_id": "new-user",
            "avatar_id": "avatar-new",
            "source_image_base64": b64_image(create_test_jpeg(400, 400)),
            "provider": "mock",
            "display_name": "Test Avatar",
            "expression_baseline": "smile",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["user_id"] == "new-user"
        assert body["avatar_id"] == "avatar-new"
        assert body["provider"] == "mock"
        assert body["expression_baseline"] == "smile"
        assert body["display_name"] == "Test Avatar"
        assert body["image_width"] == 400
        assert body["image_height"] == 400
        assert body["image_format"] == "JPEG"
        assert body["image_source"] == "upload"

    def test_create_defaults_to_neutral(self, client: TestClient):
        resp = client.post("/api/v1/avatars", json={
            "user_id": "u1",
            "avatar_id": "a1",
            "source_image_base64": b64_image(),
        })
        assert resp.status_code == 201
        assert resp.json()["expression_baseline"] == "neutral"

    def test_create_stores_image_on_disk(self, client: TestClient, tmp_path):
        _create_avatar(client, "store-test", "store-avatar")
        resp = client.get("/api/v1/avatars/store-test")
        assert resp.status_code == 200
        path = resp.json()["source_image_path"]
        assert "store-test" in path
        assert "store-avatar" in path


class TestGetAvatar:

    def test_get_existing_profile(self, client: TestClient):
        _create_avatar(client, "alice", "alice-avatar")
        resp = client.get("/api/v1/avatars/alice")
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == "alice"
        assert body["avatar_id"] == "alice-avatar"
        assert body["image_width"] >= 64
        assert body["image_height"] >= 64

    def test_get_missing_profile_returns_404(self, client: TestClient):
        resp = client.get("/api/v1/avatars/ghost-user")
        assert resp.status_code == 404
        assert resp.json()["code"] == "AVATAR_PROFILE_NOT_FOUND"


class TestDeleteAvatar:

    def test_delete_existing_profile(self, client: TestClient):
        _create_avatar(client, "del-user", "del-avatar")
        resp = client.delete("/api/v1/avatars/del-user")
        assert resp.status_code == 204

        resp = client.get("/api/v1/avatars/del-user")
        assert resp.status_code == 404

    def test_delete_missing_profile_returns_404(self, client: TestClient):
        resp = client.delete("/api/v1/avatars/nonexistent")
        assert resp.status_code == 404


class TestListAvatars:

    def test_list_empty(self, client: TestClient):
        resp = client.get("/api/v1/avatars")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_all_with_metadata(self, client: TestClient):
        _create_avatar(client, "u1", "a1")
        _create_avatar(client, "u2", "a2")
        resp = client.get("/api/v1/avatars")
        assert resp.status_code == 200
        profiles = resp.json()
        ids = {p["user_id"] for p in profiles}
        assert ids == {"u1", "u2"}
        for p in profiles:
            assert p["image_width"] > 0
            assert p["image_height"] > 0
            assert p["image_format"] in ("JPEG", "PNG")


# ---------------------------------------------------------------------------
# Identity consistency
# ---------------------------------------------------------------------------

class TestIdentityConsistency:

    def test_same_user_different_images_updates_profile(self, client: TestClient):
        img1 = create_test_jpeg(256, 256, (200, 100, 50))
        img2 = create_test_jpeg(300, 300, (50, 100, 200))

        _create_avatar(client, "user-x", "face-v1", img1)
        r1 = client.get("/api/v1/avatars/user-x")
        assert r1.json()["image_width"] == 256

        _create_avatar(client, "user-x", "face-v2", img2)
        r2 = client.get("/api/v1/avatars/user-x")
        assert r2.json()["image_width"] == 300
        assert r2.json()["avatar_id"] == "face-v2"

    def test_different_users_have_independent_profiles(self, client: TestClient):
        img_a = create_test_jpeg(256, 256, (255, 0, 0))
        img_b = create_test_jpeg(300, 300, (0, 0, 255))

        _create_avatar(client, "alice", "alice-face", img_a)
        _create_avatar(client, "bob", "bob-face", img_b)

        ra = client.get("/api/v1/avatars/alice")
        rb = client.get("/api/v1/avatars/bob")

        assert ra.json()["avatar_id"] == "alice-face"
        assert rb.json()["avatar_id"] == "bob-face"
        assert ra.json()["image_width"] == 256
        assert rb.json()["image_width"] == 300

    def test_never_creates_generic_avatar(self, client: TestClient):
        resp = client.get("/api/v1/avatars/nonexistent-user")
        assert resp.status_code == 404
        assert resp.json()["code"] == "AVATAR_PROFILE_NOT_FOUND"
