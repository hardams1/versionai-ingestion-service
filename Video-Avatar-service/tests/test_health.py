"""Tests for system endpoints: health, root."""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestHealth:

    def test_health_returns_ok(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "version" in body
        assert body["renderer_provider"] == "mock"

    def test_root_returns_service_info(self, client: TestClient):
        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert "service" in body
        assert body["docs"] == "/docs"
        assert body["renderer_provider"] == "mock"
