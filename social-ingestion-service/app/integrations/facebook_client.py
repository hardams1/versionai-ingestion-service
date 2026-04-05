from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.integrations.base_client import BasePlatformClient
from app.models.schemas import NormalizedContent

logger = logging.getLogger(__name__)

FB_AUTH_URL = "https://www.facebook.com/v19.0/dialog/oauth"
FB_TOKEN_URL = "https://graph.facebook.com/v19.0/oauth/access_token"
GRAPH_API = "https://graph.facebook.com/v19.0"

SCOPES = "public_profile,email,user_posts"


class FacebookClient(BasePlatformClient):
    platform = "facebook"

    def __init__(self) -> None:
        s = get_settings()
        self._app_id = s.facebook_app_id or ""
        self._app_secret = s.facebook_app_secret or ""

    def has_oauth_keys(self) -> bool:
        return bool(self._app_id and self._app_secret)

    def get_oauth_url(
        self, state: str, redirect_uri: str, code_challenge: Optional[str] = None
    ) -> str:
        params = {
            "client_id": self._app_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": SCOPES,
            "response_type": "code",
        }
        return f"{FB_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(
        self, code: str, redirect_uri: str, code_verifier: Optional[str] = None
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                FB_TOKEN_URL,
                params={
                    "client_id": self._app_id,
                    "client_secret": self._app_secret,
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )
            resp.raise_for_status()
            token_data = resp.json()

            me_resp = await client.get(
                f"{GRAPH_API}/me",
                params={
                    "fields": "id,name,email",
                    "access_token": token_data["access_token"],
                },
            )
            me_data = me_resp.json()

            return {
                "access_token": token_data["access_token"],
                "refresh_token": None,
                "username": me_data.get("name", ""),
                "user_id": me_data.get("id", ""),
                "expires_in": token_data.get("expires_in"),
            }

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
                    logger.warning("Facebook API %d", resp.status_code)
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
