from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.integrations.base_client import BasePlatformClient
from app.models.schemas import NormalizedContent

logger = logging.getLogger(__name__)

TIKTOK_AUTH = "https://www.tiktok.com/v2/auth/authorize"
TIKTOK_TOKEN = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_API = "https://open.tiktokapis.com/v2"


class TikTokClient(BasePlatformClient):
    platform = "tiktok"

    def __init__(self) -> None:
        s = get_settings()
        self._client_key = s.tiktok_client_key
        self._client_secret = s.tiktok_client_secret

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
                resp = await client.post(
                    f"{TIKTOK_API}/video/list/",
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={"max_count": min(max_items, 20)},
                    params={"fields": "id,title,create_time,like_count,comment_count,share_count"},
                )
                if resp.status_code != 200:
                    logger.warning("TikTok API returned %d", resp.status_code)
                    return items

                for video in resp.json().get("data", {}).get("videos", []):
                    title = video.get("title", "")
                    if not title:
                        continue

                    hashtags = [w.lstrip("#") for w in title.split() if w.startswith("#")]

                    items.append(NormalizedContent(
                        user_id=user_id,
                        platform="tiktok",
                        type="post",
                        content=title,
                        hashtags=hashtags,
                        engagement_score=self._compute_engagement(
                            likes=video.get("like_count", 0),
                            comments=video.get("comment_count", 0),
                            shares=video.get("share_count", 0),
                        ),
                        timestamp=str(video.get("create_time", "")),
                    ))
        except Exception as exc:
            logger.error("TikTok fetch failed: %s", exc)
        return items

    async def verify_token(self, access_token: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{TIKTOK_API}/user/info/",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={"fields": "display_name"},
                )
                return resp.status_code == 200
        except Exception:
            return False

    def get_oauth_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_key": self._client_key or "",
            "redirect_uri": redirect_uri,
            "scope": "user.info.basic,video.list",
            "response_type": "code",
            "state": state,
        }
        return f"{TIKTOK_AUTH}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                TIKTOK_TOKEN,
                data={
                    "client_key": self._client_key or "",
                    "client_secret": self._client_secret or "",
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
            )
            resp.raise_for_status()
            return resp.json()
