from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages per-user WebSocket connections for real-time notification delivery."""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, user_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.setdefault(user_id, []).append(ws)
        logger.info("WS connected: user=%s (total=%d)", user_id, len(self._connections[user_id]))

    def disconnect(self, user_id: str, ws: WebSocket) -> None:
        conns = self._connections.get(user_id, [])
        if ws in conns:
            conns.remove(ws)
        if not conns:
            self._connections.pop(user_id, None)
        logger.info("WS disconnected: user=%s", user_id)

    async def send_to_user(self, user_id: str, data: dict[str, Any]) -> int:
        """Send JSON payload to all of a user's active connections. Returns delivery count."""
        conns = self._connections.get(user_id, [])
        delivered = 0
        dead: list[WebSocket] = []

        for ws in conns:
            try:
                await ws.send_text(json.dumps(data))
                delivered += 1
            except Exception:
                dead.append(ws)

        for ws in dead:
            self.disconnect(user_id, ws)

        return delivered

    def is_online(self, user_id: str) -> bool:
        return bool(self._connections.get(user_id))

    @property
    def active_connections(self) -> int:
        return sum(len(c) for c in self._connections.values())

    @property
    def active_users(self) -> int:
        return len(self._connections)


ws_manager = ConnectionManager()
