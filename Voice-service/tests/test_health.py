"""Tests for system endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "tts_provider" in body


def test_root_endpoint(client: TestClient):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "VersionAI Voice Service"
    assert body["docs"] == "/docs"
