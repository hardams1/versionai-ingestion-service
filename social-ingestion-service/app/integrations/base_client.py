from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.models.schemas import NormalizedContent

logger = logging.getLogger(__name__)


class BasePlatformClient(ABC):
    """Abstract base class for social media platform adapters."""

    platform: str = ""

    @abstractmethod
    async def fetch_user_content(
        self,
        access_token: str,
        user_id: str,
        max_items: int = 100,
        since: Optional[str] = None,
    ) -> List[NormalizedContent]:
        """Fetch and normalize user content from the platform."""
        ...

    @abstractmethod
    async def verify_token(self, access_token: str) -> bool:
        """Check if the access token is still valid."""
        ...

    @abstractmethod
    def get_oauth_url(self, state: str, redirect_uri: str) -> str:
        """Generate the OAuth authorization URL."""
        ...

    @abstractmethod
    async def exchange_code(
        self, code: str, redirect_uri: str
    ) -> Dict[str, Any]:
        """Exchange an auth code for tokens. Returns dict with access_token, etc."""
        ...

    def _compute_engagement(
        self, likes: int = 0, comments: int = 0, shares: int = 0
    ) -> float:
        return round(likes * 1.0 + comments * 2.0 + shares * 3.0, 2)
