"""Tests for voice profile CRUD endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_create_profile(client: TestClient):
    resp = client.post("/api/v1/profiles", json={
        "user_id": "user-1",
        "voice_id": "alloy",
        "provider": "openai",
        "display_name": "Alice",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["user_id"] == "user-1"
    assert body["voice_id"] == "alloy"
    assert body["provider"] == "openai"
    assert body["display_name"] == "Alice"


def test_get_profile_after_create(client: TestClient):
    client.post("/api/v1/profiles", json={
        "user_id": "user-2",
        "voice_id": "echo",
        "provider": "openai",
    })
    resp = client.get("/api/v1/profiles/user-2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user_id"] == "user-2"
    assert body["voice_id"] == "echo"


def test_get_profile_not_found(client: TestClient):
    resp = client.get("/api/v1/profiles/nonexistent-user")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "VOICE_PROFILE_NOT_FOUND"


def test_list_profiles_empty(client: TestClient):
    resp = client.get("/api/v1/profiles")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_profiles_returns_all(client: TestClient):
    client.post("/api/v1/profiles", json={"user_id": "a", "voice_id": "alloy", "provider": "openai"})
    client.post("/api/v1/profiles", json={"user_id": "b", "voice_id": "nova", "provider": "openai"})
    resp = client.get("/api/v1/profiles")
    assert resp.status_code == 200
    ids = {p["user_id"] for p in resp.json()}
    assert ids == {"a", "b"}


def test_delete_profile(client: TestClient):
    client.post("/api/v1/profiles", json={"user_id": "del-me", "voice_id": "alloy", "provider": "openai"})
    resp = client.delete("/api/v1/profiles/del-me")
    assert resp.status_code == 204
    resp = client.get("/api/v1/profiles/del-me")
    assert resp.status_code == 404


def test_delete_nonexistent_profile(client: TestClient):
    resp = client.delete("/api/v1/profiles/ghost")
    assert resp.status_code == 404


def test_update_profile_overwrites(client: TestClient):
    client.post("/api/v1/profiles", json={"user_id": "u1", "voice_id": "alloy", "provider": "openai"})
    client.post("/api/v1/profiles", json={"user_id": "u1", "voice_id": "shimmer", "provider": "openai"})
    resp = client.get("/api/v1/profiles/u1")
    assert resp.json()["voice_id"] == "shimmer"
