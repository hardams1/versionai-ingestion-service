from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(5.0, connect=3.0)


class SiblingServiceClient:
    """
    Lightweight async client for health-checking sibling microservices.
    Used by the /health endpoint to report full system status.
    """

    def __init__(self, settings: Settings) -> None:
        self._ingestion_url = settings.ingestion_service_url
        self._processing_url = settings.processing_service_url
        self._voice_url = settings.voice_service_url

    async def check_ingestion(self) -> dict:
        return await self._check("ingestion", self._ingestion_url)

    async def check_processing(self) -> dict:
        return await self._check("processing", self._processing_url)

    async def check_voice(self) -> dict:
        return await self._check("voice", self._voice_url)

    @staticmethod
    async def _check(name: str, base_url: str | None) -> dict:
        if not base_url:
            return {"status": "not_configured"}

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(f"{base_url.rstrip('/')}/health")
                if resp.status_code == 200:
                    return {"status": "healthy", "detail": resp.json()}
                return {"status": "unhealthy", "detail": f"HTTP {resp.status_code}"}
        except httpx.TimeoutException:
            return {"status": "timeout"}
        except Exception as exc:
            return {"status": "unreachable", "detail": str(exc)}
