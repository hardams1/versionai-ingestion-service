from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

import httpx

from app.utils.exceptions import BrainServiceError

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


class BrainClient:
    """HTTP client for the AI Brain Service (:8002)."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.brain_service_url.rstrip("/")
        self._timeout = httpx.Timeout(settings.brain_timeout, connect=10.0)
        self._health_timeout = httpx.Timeout(settings.health_check_timeout, connect=3.0)

    async def chat(
        self,
        user_id: str,
        query: str,
        *,
        conversation_id: str | None = None,
        personality_id: str | None = None,
        include_sources: bool = True,
    ) -> dict[str, Any]:
        """Call Brain /api/v1/chat/ and return the full ChatResponse dict."""
        url = f"{self._base_url}/api/v1/chat/"
        payload: dict[str, Any] = {
            "user_id": user_id,
            "query": query,
            "include_sources": include_sources,
            "include_audio": False,
            "include_video": False,
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id
        if personality_id:
            payload["personality_id"] = personality_id

        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=payload)
                elapsed_ms = (time.perf_counter() - start) * 1000

                if resp.status_code != 200:
                    raise BrainServiceError(
                        f"Brain returned HTTP {resp.status_code}: {resp.text[:500]}"
                    )

                data = resp.json()
                data["_brain_latency_ms"] = round(elapsed_ms, 1)
                logger.info(
                    "Brain chat OK: user=%s, conv=%s, model=%s, latency=%.0fms",
                    user_id, data.get("conversation_id"), data.get("model_used"), elapsed_ms,
                )
                return data

        except httpx.TimeoutException as exc:
            raise BrainServiceError(f"Brain service timeout: {exc}") from exc
        except BrainServiceError:
            raise
        except Exception as exc:
            raise BrainServiceError(f"Brain service unreachable: {exc}") from exc

    async def health(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=self._health_timeout) as client:
                resp = await client.get(f"{self._base_url}/health")
                if resp.status_code == 200:
                    return {"status": "healthy", "detail": resp.json().get("status")}
                return {"status": "unhealthy", "detail": f"HTTP {resp.status_code}"}
        except Exception as exc:
            return {"status": "unreachable", "detail": str(exc)}
