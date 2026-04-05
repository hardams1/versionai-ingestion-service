from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.integrations.base_client import BasePlatformClient
from app.models.schemas import NormalizedContent

logger = logging.getLogger(__name__)

GRAPH_API = "https://graph.facebook.com/v19.0"


class FacebookClient(BasePlatformClient):
    platform = "facebook"

    def __init__(self) -> None:
        s = get_settings()
        self._app_id = s.facebook_app_id
        self._app_secret = s.facebook_app_secret

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
                params: Dict[str, Any] = {
                    "fields": "message,created_time,likes.summary(true),comments.summary(true),shares",
                    "limit": min(max_items, 100),
                    "access_token": access_token,
                }
                resp = await client.get(f"{GRAPH_API}/me/posts", params=params)
                if resp.status_code != 200:
                    logger.warning("Facebook API returned %d", resp.status_code)
                    return items

                for post in resp.json().get("data", []):
                    message = post.get("message", "")
                    if not message:
                        continue
                    likes = post.get("likes", {}).get("summary", {}).get("total_count", 0)
                    comments = post.get("comments", {}).get("summary", {}).get("total_count", 0)
                    shares = post.get("shares", {}).get("count", 0)

                    items.append(NormalizedContent(
                        user_id=user_id,
                        platform="facebook",
                        type="post",
                        content=message,
                        engagement_score=self._compute_engagement(likes, comments, shares),
                        timestamp=post.get("created_time", ""),
                    ))
        except Exception as exc:
            logger.error("Facebook fetch failed: %s", exc)
        return items

    async def verify_token(self, access_token: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{GRAPH_API}/me",
                    params={"access_token": access_token},
                )
                return resp.status_code == 200
        except Exception:
            return False

    def get_oauth_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": self._app_id or "",
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": "public_profile,user_posts",
        }
        return f"https://www.facebook.com/v19.0/dialog/oauth?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{GRAPH_API}/oauth/access_token",
                params={
                    "client_id": self._app_id or "",
                    "client_secret": self._app_secret or "",
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )
            resp.raise_for_status()
            return resp.json()
