from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.channels.websocket_manager import ws_manager
from app.core.config import get_settings
from app.core.security import decode_token

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/notifications")
async def notifications_websocket(ws: WebSocket) -> None:
    """
    WebSocket endpoint for real-time notification delivery.
    Client sends {"token": "..."} as the first message to authenticate.
    """
    await ws.accept()
    settings = get_settings()

    try:
        auth_msg = await ws.receive_json()
        token = auth_msg.get("token")
        if not token:
            await ws.send_json({"error": "token required"})
            await ws.close(code=4001)
            return

        payload = decode_token(token, settings)
        if not payload or "sub" not in payload:
            await ws.send_json({"error": "invalid token"})
            await ws.close(code=4001)
            return

        user_id = payload["sub"]
    except Exception:
        await ws.close(code=4001)
        return

    ws_manager._connections.setdefault(user_id, []).append(ws)
    logger.info("WS authenticated: user=%s", user_id)
    await ws.send_json({"type": "connected", "user_id": user_id})

    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(user_id, ws)
