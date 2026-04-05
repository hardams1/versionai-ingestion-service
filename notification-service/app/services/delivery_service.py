from __future__ import annotations

import logging
from typing import Any

from app.channels.websocket_manager import ws_manager

logger = logging.getLogger(__name__)


async def deliver(user_id: str, notification: dict[str, Any]) -> str:
    """Attempt delivery via the best available channel. Returns channel used."""

    # 1. WebSocket (instant)
    if ws_manager.is_online(user_id):
        count = await ws_manager.send_to_user(user_id, {
            "type": "notification",
            "data": notification,
        })
        if count > 0:
            logger.info("Delivered via WS to user=%s (%d connections)", user_id, count)
            return "websocket"

    # 2. Push notification (placeholder — mobile push integration point)
    # In production, integrate with FCM / APNs here
    logger.debug("Push delivery placeholder for user=%s", user_id)

    # 3. Email fallback (placeholder)
    logger.debug("Email delivery placeholder for user=%s", user_id)

    return "stored"
