from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.integrations.base_client import BasePlatformClient
from app.models.schemas import NormalizedContent

logger = logging.getLogger(__name__)

TWITTER_API = "https://api.twitter.com/2"
TWITTER_AUTH = "https://twitter.com/i/oauth2/authorize"
TWITTER_TOKEN = "https://api.twitter.com/2/oauth2/token"


class TwitterClient(BasePlatformClient):
    platform = "twitter"

    def __init__(self) -> None:
        s = get_settings()
        self._client_id = s.twitter_client_id
        self._client_secret = s.twitter_client_secret

    async def fetch_user_content(
        self,
        access_token: str,
        user_id: str,
        max_items: int = 100,
        since: Optional[str] = None,
    ) -> List[NormalizedContent]:
        headers = {"Authorization": f"Bearer {access_token}"}
        items: List[NormalizedContent] = []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                params: Dict[str, Any] = {
                    "max_results": min(max_items, 100),
                    "tweet.fields": "created_at,public_metrics,entities",
                }
                if since:
                    params["start_time"] = since

                resp = await client.get(
                    f"{TWITTER_API}/users/me/tweets",
                    headers=headers,
                    params=params,
                )
                if resp.status_code != 200:
                    logger.warning("Twitter API returned %d: %s", resp.status_code, resp.text[:200])
                    return items

                data = resp.json().get("data", [])
                for tweet in data:
                    metrics = tweet.get("public_metrics", {})
                    entities = tweet.get("entities", {})
                    hashtags = [h["tag"] for h in entities.get("hashtags", [])]
                    mentions = [m["username"] for m in entities.get("mentions", [])]

                    items.append(NormalizedContent(
                        user_id=user_id,
                        platform="twitter",
                        type="post",
                        content=tweet.get("text", ""),
                        topics=[],
                        hashtags=hashtags,
                        mentions=mentions,
                        engagement_score=self._compute_engagement(
                            likes=metrics.get("like_count", 0),
                            comments=metrics.get("reply_count", 0),
                            shares=metrics.get("retweet_count", 0),
                        ),
                        timestamp=tweet.get("created_at", ""),
                    ))
        except Exception as exc:
            logger.error("Twitter fetch failed: %s", exc)

        return items

    async def verify_token(self, access_token: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{TWITTER_API}/users/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                return resp.status_code == 200
        except Exception:
            return False

    def get_oauth_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self._client_id or "",
            "redirect_uri": redirect_uri,
            "scope": "tweet.read users.read offline.access",
            "state": state,
            "code_challenge": "challenge",
            "code_challenge_method": "plain",
        }
        return f"{TWITTER_AUTH}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                TWITTER_TOKEN,
                data={
                    "code": code,
                    "grant_type": "authorization_code",
                    "client_id": self._client_id or "",
                    "redirect_uri": redirect_uri,
                    "code_verifier": "challenge",
                },
                auth=(self._client_id or "", self._client_secret or ""),
            )
            resp.raise_for_status()
            return resp.json()
