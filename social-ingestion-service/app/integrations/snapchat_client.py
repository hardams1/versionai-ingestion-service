from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.integrations.base_client import BasePlatformClient
from app.models.schemas import NormalizedContent

logger = logging.getLogger(__name__)

SNAP_AUTH_URL = "https://accounts.snapchat.com/accounts/oauth2/auth"
SNAP_TOKEN_URL = "https://accounts.snapchat.com/accounts/oauth2/token"
SNAP_API = "https://kit.snapchat.com/v1"

SCOPES = "https://auth.snapchat.com/oauth2/api/user.display_name https://auth.snapchat.com/oauth2/api/user.bitmoji.avatar"


class SnapchatClient(BasePlatformClient):
    """Snapchat adapter using Snap Kit Login."""

    platform = "snapchat"

    def __init__(self) -> None:
        s = get_settings()
        self._client_id = s.snapchat_client_id or ""
        self._client_secret = s.snapchat_client_secret or ""

    def has_oauth_keys(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def get_oauth_url(
        self, state: str, redirect_uri: str, code_challenge: Optional[str] = None
    ) -> str:
        params = {
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPES,
            "state": state,
        }
        return f"{SNAP_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(
        self, code: str, redirect_uri: str, code_verifier: Optional[str] = None
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                SNAP_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            )
            resp.raise_for_status()
            token_data = resp.json()

            me_resp = await client.get(
                f"{SNAP_API}/me",
                headers={"Authorization": f"Bearer {token_data['access_token']}"},
            )
            me_data = me_resp.json().get("data", me_resp.json())

            return {
                "access_token": token_data["access_token"],
                "refresh_token": token_data.get("refresh_token"),
                "username": me_data.get("displayName", me_data.get("display_name", "")),
                "user_id": me_data.get("externalId", me_data.get("id", "")),
                "expires_in": token_data.get("expires_in"),
            }

    async def fetch_user_content(
        self,
        access_token: str,
        user_id: str,
        max_items: int = 100,
        since: Optional[str] = None,
    ) -> List[NormalizedContent]:
        logger.info("Snapchat content fetch — limited public API, returning empty")
        return []

    async def verify_token(self, access_token: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{SNAP_API}/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                return resp.status_code == 200
        except Exception:
            return False
