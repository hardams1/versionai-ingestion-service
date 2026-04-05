from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.integrations.base_client import BasePlatformClient
from app.models.schemas import NormalizedContent

logger = logging.getLogger(__name__)

TWITTER_AUTH_URL = "https://twitter.com/i/oauth2/authorize"
TWITTER_TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
TWITTER_API = "https://api.twitter.com/2"

SCOPES = "tweet.read users.read follows.read offline.access"


class TwitterClient(BasePlatformClient):
    platform = "twitter"

    def __init__(self) -> None:
        s = get_settings()
        self._client_id = s.twitter_client_id or ""
        self._client_secret = s.twitter_client_secret or ""

    def has_oauth_keys(self) -> bool:
        return bool(self._client_id)

    def get_oauth_url(
        self, state: str, redirect_uri: str, code_challenge: Optional[str] = None
    ) -> str:
        params = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "scope": SCOPES,
            "state": state,
            "code_challenge_method": "S256",
            "code_challenge": code_challenge or state,
        }
        return f"{TWITTER_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(
        self, code: str, redirect_uri: str, code_verifier: Optional[str] = None
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                TWITTER_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": self._client_id,
                    "code_verifier": code_verifier or "",
                },
                auth=(self._client_id, self._client_secret),
            )
            resp.raise_for_status()
            token_data = resp.json()

            me_resp = await client.get(
                f"{TWITTER_API}/users/me",
                headers={"Authorization": f"Bearer {token_data['access_token']}"},
            )
            me_data = me_resp.json().get("data", {})

            return {
                "access_token": token_data["access_token"],
                "refresh_token": token_data.get("refresh_token"),
                "username": me_data.get("username", ""),
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
                    logger.warning("Twitter API %d: %s", resp.status_code, resp.text[:200])
                    return items

                for tweet in resp.json().get("data", []):
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
