from __future__ import annotations

import logging

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class VideoAvatarClient:
    """Syncs profile image to the Video Avatar Service as the user's avatar."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.video_avatar_service_url.rstrip("/")

    async def sync_avatar(
        self, user_id: str, image_base64: str, display_name: str | None = None
    ) -> bool:
        url = f"{self._base_url}/api/v1/avatars"
        payload = {
            "user_id": user_id,
            "avatar_id": f"avatar-{user_id}",
            "source_image_base64": image_base64,
            "provider": "mock",
            "display_name": display_name,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload)

                if resp.status_code == 409:
                    logger.info("Avatar already exists for user=%s, updating via delete+create", user_id)
                    await client.delete(f"{self._base_url}/api/v1/avatars/{user_id}")
                    resp = await client.post(url, json=payload)

                if resp.status_code in (200, 201):
                    logger.info("Avatar synced for user=%s", user_id)
                    return True
                else:
                    logger.warning(
                        "Avatar sync failed for user=%s: HTTP %d %s",
                        user_id, resp.status_code, resp.text[:200],
                    )
                    return False
        except Exception as exc:
            logger.error("Avatar sync error for user=%s: %s", user_id, exc)
            return False
