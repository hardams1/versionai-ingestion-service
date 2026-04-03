from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import httpx

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class AccessResult:
    allowed: bool
    reason: str
    remaining_questions: Optional[int] = None


class SocialGraphClient:
    """HTTP client for the Social Graph Service (:8010)."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.social_graph_service_url.rstrip("/")
        self._timeout = httpx.Timeout(10.0, connect=5.0)

    async def check_access(self, requester_id: str, target_user_id: str) -> AccessResult:
        """Check AI access permission and rate limit."""
        if requester_id == target_user_id:
            return AccessResult(allowed=True, reason="Owner", remaining_questions=None)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/access/check",
                    json={
                        "requester_id": requester_id,
                        "target_user_id": target_user_id,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return AccessResult(
                        allowed=data["allowed"],
                        reason=data["reason"],
                        remaining_questions=data.get("remaining_questions"),
                    )
                logger.warning("Social graph access check failed: HTTP %d", resp.status_code)
        except Exception as exc:
            logger.debug("Social graph service unreachable: %s", exc)

        return AccessResult(allowed=True, reason="Social graph service unavailable — defaulting to allow")

    async def health(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0)) as client:
                resp = await client.get(f"{self._base_url}/health")
                if resp.status_code == 200:
                    return {"status": "healthy", "detail": resp.json().get("status")}
                return {"status": "unhealthy", "detail": f"HTTP {resp.status_code}"}
        except Exception as exc:
            return {"status": "unreachable", "detail": str(exc)}
