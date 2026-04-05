from __future__ import annotations

from typing import Dict

from app.integrations.base_client import BasePlatformClient
from app.integrations.facebook_client import FacebookClient
from app.integrations.instagram_client import InstagramClient
from app.integrations.snapchat_client import SnapchatClient
from app.integrations.tiktok_client import TikTokClient
from app.integrations.twitter_client import TwitterClient

_clients: Dict[str, BasePlatformClient] = {}


def get_platform_client(platform: str) -> BasePlatformClient:
    if platform not in _clients:
        registry = {
            "twitter": TwitterClient,
            "facebook": FacebookClient,
            "instagram": InstagramClient,
            "tiktok": TikTokClient,
            "snapchat": SnapchatClient,
        }
        cls = registry.get(platform)
        if not cls:
            raise ValueError(f"Unsupported platform: {platform}")
        _clients[platform] = cls()
    return _clients[platform]


SUPPORTED_PLATFORMS = ["twitter", "facebook", "instagram", "tiktok", "snapchat"]
