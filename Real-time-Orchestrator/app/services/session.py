from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.models.enums import SessionState

logger = logging.getLogger(__name__)


class Session:
    """Tracks per-connection state for a WebSocket session."""

    __slots__ = ("session_id", "user_id", "state", "connected_at", "last_request_id")

    def __init__(self, session_id: str, user_id: str | None = None) -> None:
        self.session_id = session_id
        self.user_id = user_id
        self.state = SessionState.CONNECTED
        self.connected_at = datetime.now(timezone.utc)
        self.last_request_id: str | None = None


class SessionManager:
    """Thread-safe in-memory session tracker."""

    def __init__(self, max_sessions: int = 100) -> None:
        self._sessions: dict[str, Session] = {}
        self._max = max_sessions

    @property
    def active_count(self) -> int:
        return len(self._sessions)

    def can_accept(self) -> bool:
        return len(self._sessions) < self._max

    def create(self, session_id: str, user_id: str | None = None) -> Session:
        session = Session(session_id, user_id)
        self._sessions[session_id] = session
        logger.info("Session created: %s (active=%d)", session_id, self.active_count)
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def remove(self, session_id: str) -> None:
        removed = self._sessions.pop(session_id, None)
        if removed:
            logger.info("Session removed: %s (active=%d)", session_id, self.active_count)
