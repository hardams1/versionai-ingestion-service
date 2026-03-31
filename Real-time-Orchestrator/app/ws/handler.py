from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.models.enums import MessageType, SessionState
from app.models.schemas import WSIncomingMessage, WSOutgoingMessage
from app.utils.exceptions import QueryTooLongError, SessionLimitError

if TYPE_CHECKING:
    from app.config import Settings
    from app.services.pipeline import OrchestrationPipeline
    from app.services.session import SessionManager

logger = logging.getLogger(__name__)


class WebSocketHandler:
    """Manages a single WebSocket connection's lifecycle.

    Protocol:
      Client → Server (JSON):
        {"type": "query", "user_id": "...", "query": "...", ...}
        {"type": "ping"}

      Server → Client (JSON):
        {"type": "ack",      "request_id": "...", "data": {...}}
        {"type": "text",     "request_id": "...", "data": {"response": "..."}}
        {"type": "audio",    "request_id": "...", "data": {"audio_base64": "..."}}
        {"type": "video",    "request_id": "...", "data": {"video_base64": "..."}}
        {"type": "stage",    "request_id": "...", "data": {"stage": "brain"}}
        {"type": "complete", "request_id": "...", "data": {"total_latency_ms": ...}}
        {"type": "error",    "request_id": "...", "data": {"detail": "..."}}
        {"type": "pong"}
    """

    def __init__(
        self,
        pipeline: OrchestrationPipeline,
        session_mgr: SessionManager,
        settings: Settings,
    ) -> None:
        self._pipeline = pipeline
        self._sessions = session_mgr
        self._settings = settings

    async def handle(self, websocket: WebSocket) -> None:
        if not self._sessions.can_accept():
            await websocket.close(code=1013, reason="Server at capacity")
            raise SessionLimitError(self._settings.max_concurrent_sessions)

        await websocket.accept()
        session_id = str(uuid.uuid4())
        session = self._sessions.create(session_id)

        logger.info("WebSocket connected: session=%s", session_id)

        try:
            while True:
                raw = await websocket.receive_json()
                await self._dispatch(websocket, session_id, raw)
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected: session=%s", session_id)
        except Exception as exc:
            logger.exception("WebSocket error: session=%s %s", session_id, exc)
            try:
                await self._send(websocket, WSOutgoingMessage(
                    type=MessageType.ERROR,
                    data={"detail": "Internal server error"},
                ))
            except Exception:
                pass
        finally:
            session.state = SessionState.DISCONNECTED
            self._sessions.remove(session_id)

    async def _dispatch(
        self,
        ws: WebSocket,
        session_id: str,
        raw: dict,
    ) -> None:
        msg_type = raw.get("type")

        if msg_type == MessageType.PING.value:
            await self._send(ws, WSOutgoingMessage(type=MessageType.PONG))
            return

        if msg_type == MessageType.QUERY.value:
            await self._handle_query(ws, session_id, raw)
            return

        await self._send(ws, WSOutgoingMessage(
            type=MessageType.ERROR,
            data={"detail": f"Unknown message type: {msg_type}"},
        ))

    async def _handle_query(
        self,
        ws: WebSocket,
        session_id: str,
        raw: dict,
    ) -> None:
        try:
            msg = WSIncomingMessage(**raw)
        except (ValidationError, TypeError) as exc:
            await self._send(ws, WSOutgoingMessage(
                type=MessageType.ERROR,
                data={"detail": f"Invalid message: {exc}"},
            ))
            return

        if not msg.user_id or not msg.query:
            await self._send(ws, WSOutgoingMessage(
                type=MessageType.ERROR,
                data={"detail": "user_id and query are required"},
            ))
            return

        if len(msg.query) > self._settings.max_query_length:
            await self._send(ws, WSOutgoingMessage(
                type=MessageType.ERROR,
                data={"detail": f"Query too long ({len(msg.query)} > {self._settings.max_query_length})"},
            ))
            return

        session = self._sessions.get(session_id)
        if session:
            session.state = SessionState.PROCESSING
            session.user_id = msg.user_id

        request_id = msg.request_id or str(uuid.uuid4())

        async for out_msg in self._pipeline.run_streaming(
            user_id=msg.user_id,
            query=msg.query,
            conversation_id=msg.conversation_id,
            personality_id=msg.personality_id,
            include_audio=msg.include_audio,
            include_video=msg.include_video,
            audio_format=self._settings.default_audio_format,
            video_format=self._settings.default_video_format,
            request_id=request_id,
        ):
            await self._send(ws, out_msg)

        if session:
            session.state = SessionState.IDLE
            session.last_request_id = request_id

    @staticmethod
    async def _send(ws: WebSocket, msg: WSOutgoingMessage) -> None:
        await ws.send_json(msg.model_dump(mode="json"))
