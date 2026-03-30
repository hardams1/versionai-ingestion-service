from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_health(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body


@pytest.mark.anyio
async def test_root(client: AsyncClient) -> None:
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "service" in resp.json()


@pytest.mark.anyio
@patch("app.services.storage.S3StorageService.upload", new_callable=AsyncMock, return_value="uploads/video/2025/01/01/abc123_test.mp4")
@patch("app.services.queue.SQSPublisher.publish", new_callable=AsyncMock, return_value="msg-123")
async def test_upload_video(mock_publish: AsyncMock, mock_upload: AsyncMock, client: AsyncClient) -> None:
    mp4_header = bytes.fromhex(
        "0000001C667479706D703432"
        "00000000"
        "6D70343269736F6D"
    )
    payload = mp4_header + b"\x00" * 1024

    resp = await client.post(
        "/api/v1/upload/",
        files={"file": ("test.mp4", payload, "video/mp4")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["filename"] == "test.mp4"
    assert body["status"] == "queued"
    assert "ingestion_id" in body
    mock_upload.assert_awaited_once()
    mock_publish.assert_awaited_once()


@pytest.mark.anyio
async def test_upload_empty_file(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/upload/",
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_upload_dangerous_extension(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/upload/",
        files={"file": ("malware.exe", b"\x00" * 100, "application/octet-stream")},
    )
    assert resp.status_code == 415
