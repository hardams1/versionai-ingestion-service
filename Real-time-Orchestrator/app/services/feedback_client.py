from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class FeedbackClient:
    """Async client for the Feedback Intelligence Service."""

    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def capture_question(
        self,
        target_user_id: str,
        asker_user_id: str,
        question: str,
        session_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Fire-and-forget capture. Returns response dict or None on failure."""
        url = f"{self._base_url}/feedback/capture"
        payload = {
            "target_user_id": target_user_id,
            "asker_user_id": asker_user_id,
            "question": question,
            "session_id": session_id,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    return resp.json()
                logger.warning("Feedback capture returned %d", resp.status_code)
        except Exception as exc:
            logger.debug("Feedback capture failed (non-fatal): %s", exc)
        return None

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self._base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False
