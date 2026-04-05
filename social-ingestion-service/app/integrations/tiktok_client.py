from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.integrations.base_client import BasePlatformClient
from app.models.schemas import NormalizedContent

logger = logging.getLogger(__name__)

TT_AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TT_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_API = "https://open.tiktokapis.com/v2"

SCOPES = "user.info.basic,video.list"


class TikTokClient(BasePlatformClient):
    platform = "tiktok"

    def __init__(self) -> None:
        s = get_settings()
        self._client_key = s.tiktok_client_key or ""
        self._client_secret = s.tiktok_client_secret or ""

    def has_oauth_keys(self) -> bool:
        return bool(self._client_key and self._client_secret)

    def get_oauth_url(
        self, state: str, redirect_uri: str, code_challenge: Optional[str] = None
    ) -> str:
        params = {
            "client_key": self._client_key,
            "redirect_uri": redirect_uri,
            "scope": SCOPES,
            "response_type": "code",
            "state": state,
        }
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
        return f"{TT_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(
        self, code: str, redirect_uri: str, code_verifier: Optional[str] = None
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            body: Dict[str, str] = {
                "client_key": self._client_key,
                "client_secret": self._client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            }
            if code_verifier:
                body["code_verifier"] = code_verifier

            resp = await client.post(TT_TOKEN_URL, data=body)
            resp.raise_for_status()
            token_data = resp.json()

            user_resp = await client.get(
                f"{TIKTOK_API}/user/info/",
                headers={"Authorization": f"Bearer {token_data['access_token']}"},
                params={"fields": "open_id,display_name,avatar_url"},
            )
            user_data = user_resp.json().get("data", {}).get("user", {})

            return {
                "access_token": token_data["access_token"],
                "refresh_token": token_data.get("refresh_token"),
                "username": user_data.get("display_name", ""),
                "user_id": user_data.get("open_id", token_data.get("open_id", "")),
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
                resp = await client.post(
                    f"{TIKTOK_API}/video/list/",
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={"max_count": min(max_items, 20)},
                    params={"fields": "id,title,create_time,like_count,comment_count,share_count"},
                )
                if resp.status_code != 200:
                    logger.warning("TikTok API %d", resp.status_code)
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
                    params={"fields": "open_id"},
                )
                return resp.status_code == 200
        except Exception:
            return False
