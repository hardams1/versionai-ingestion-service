from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.integrations.base_client import BasePlatformClient
from app.models.schemas import NormalizedContent

logger = logging.getLogger(__name__)

IG_AUTH_URL = "https://api.instagram.com/oauth/authorize"
IG_TOKEN_URL = "https://api.instagram.com/oauth/access_token"
IG_GRAPH_URL = "https://graph.instagram.com"

SCOPES = "user_profile,user_media"


class InstagramClient(BasePlatformClient):
    platform = "instagram"

    def __init__(self) -> None:
        s = get_settings()
        self._app_id = s.instagram_app_id or ""
        self._app_secret = s.instagram_app_secret or ""

    def has_oauth_keys(self) -> bool:
        return bool(self._app_id and self._app_secret)

    def get_oauth_url(
        self, state: str, redirect_uri: str, code_challenge: Optional[str] = None
    ) -> str:
        params = {
            "client_id": self._app_id,
            "redirect_uri": redirect_uri,
            "scope": SCOPES,
            "response_type": "code",
            "state": state,
        }
        return f"{IG_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(
        self, code: str, redirect_uri: str, code_verifier: Optional[str] = None
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                IG_TOKEN_URL,
                data={
                    "client_id": self._app_id,
                    "client_secret": self._app_secret,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )
            resp.raise_for_status()
            token_data = resp.json()

            me_resp = await client.get(
                f"{IG_GRAPH_URL}/me",
                params={
                    "fields": "id,username",
                    "access_token": token_data["access_token"],
                },
            )
            me_data = me_resp.json()

            return {
                "access_token": token_data["access_token"],
                "refresh_token": None,
                "username": me_data.get("username", ""),
                "user_id": str(me_data.get("id", token_data.get("user_id", ""))),
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
                resp = await client.get(
                    f"{IG_GRAPH_URL}/me/media",
                    params={
                        "fields": "id,caption,timestamp,like_count,comments_count,media_type",
                        "limit": min(max_items, 100),
                        "access_token": access_token,
                    },
                )
                if resp.status_code != 200:
                    logger.warning("Instagram API %d", resp.status_code)
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
                    f"{IG_GRAPH_URL}/me",
                    params={"fields": "id", "access_token": access_token},
                )
                return resp.status_code == 200
        except Exception:
            return False
