from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


class SettingsClient:
    """Fetches user output preferences from the Profile Settings Service."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.profile_settings_service_url.rstrip("/")

    async def get_user_output_mode(self, user_id: str) -> dict | None:
        """Fetch user settings. Returns None if user has no saved settings."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base_url}/settings/{user_id}/public")
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "output_mode": data.get("output_mode", "video"),
                        "response_length": data.get("response_length", "medium"),
                        "creativity_level": data.get("creativity_level", "medium"),
                    }
        except Exception as exc:
            logger.debug("Settings fetch failed for user=%s: %s", user_id, exc)
        return None
