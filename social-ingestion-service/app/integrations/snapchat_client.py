from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.integrations.base_client import BasePlatformClient
from app.models.schemas import NormalizedContent

logger = logging.getLogger(__name__)


class SnapchatClient(BasePlatformClient):
    """Placeholder adapter for Snapchat.

    Snapchat's content API has very limited public access. This adapter
    provides the interface so it can be swapped in when API access is granted.
    """

    platform = "snapchat"

    async def fetch_user_content(
        self,
        access_token: str,
        user_id: str,
        max_items: int = 100,
        since: Optional[str] = None,
    ) -> List[NormalizedContent]:
        logger.info("Snapchat content fetch not yet implemented — placeholder")
        return []

    async def verify_token(self, access_token: str) -> bool:
        return bool(access_token)

    def get_oauth_url(self, state: str, redirect_uri: str) -> str:
        return ""

    async def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        return {"access_token": "", "note": "Snapchat integration pending API access"}
