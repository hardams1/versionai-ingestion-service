from __future__ import annotations

import logging

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class AIBrainClient:
    """Notifies the AI Brain Service of visual identity updates."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.brain_service_url.rstrip("/")

    async def update_visual_profile(self, user_id: str, image_url: str) -> bool:
        """Inform the brain service that the user has a new visual identity."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self._base_url}/api/v1/profile/visual-identity",
                    json={"user_id": user_id, "image_url": image_url},
                )
                if resp.status_code in (200, 201, 204, 404):
                    logger.info("Brain notified of visual identity for user=%s", user_id)
                    return True
                logger.warning("Brain notification failed: HTTP %d", resp.status_code)
                return False
        except Exception as exc:
            logger.warning("Brain notification error (non-fatal): %s", exc)
            return False
