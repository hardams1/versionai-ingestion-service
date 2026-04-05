from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.integrations.base_client import BasePlatformClient
from app.models.schemas import NormalizedContent

logger = logging.getLogger(__name__)

INSTAGRAM_GRAPH = "https://graph.instagram.com"


class InstagramClient(BasePlatformClient):
    platform = "instagram"

    def __init__(self) -> None:
        s = get_settings()
        self._app_id = s.instagram_app_id
        self._app_secret = s.instagram_app_secret

    async def fetch_user_content(
        self,
        access_token: str,
        user_id: str,
        max_items: int = 100,
        since: Optional[str] = None,
    ) -> List[NormalizedContent]:
        items: List[NormalizedContent] = []
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{INSTAGRAM_GRAPH}/me/media",
                    params={
                        "fields": "id,caption,timestamp,like_count,comments_count,media_type",
                        "limit": min(max_items, 100),
                        "access_token": access_token,
                    },
                )
                if resp.status_code != 200:
                    logger.warning("Instagram API returned %d", resp.status_code)
                    return items

                for media in resp.json().get("data", []):
                    caption = media.get("caption", "")
                    if not caption:
                        continue

                    hashtags = [w.lstrip("#") for w in caption.split() if w.startswith("#")]
                    mentions = [w.lstrip("@") for w in caption.split() if w.startswith("@")]

                    items.append(NormalizedContent(
                        user_id=user_id,
                        platform="instagram",
                        type="post",
                        content=caption,
                        hashtags=hashtags,
                        mentions=mentions,
                        engagement_score=self._compute_engagement(
                            likes=media.get("like_count", 0),
                            comments=media.get("comments_count", 0),
                        ),
                        timestamp=media.get("timestamp", ""),
                    ))
        except Exception as exc:
            logger.error("Instagram fetch failed: %s", exc)
        return items

    async def verify_token(self, access_token: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{INSTAGRAM_GRAPH}/me",
                    params={"fields": "id,username", "access_token": access_token},
                )
                return resp.status_code == 200
        except Exception:
            return False

    def get_oauth_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": self._app_id or "",
            "redirect_uri": redirect_uri,
            "scope": "user_profile,user_media",
            "response_type": "code",
            "state": state,
        }
        return f"https://api.instagram.com/oauth/authorize?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.instagram.com/oauth/access_token",
                data={
                    "client_id": self._app_id or "",
                    "client_secret": self._app_secret or "",
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )
            resp.raise_for_status()
            return resp.json()
