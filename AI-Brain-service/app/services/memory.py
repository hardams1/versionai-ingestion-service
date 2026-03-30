from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.models.enums import MessageRole
from app.models.schemas import ChatMessage, ConversationHistory, MemoryStatusResponse

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


class ConversationMemory:
    """
    Redis-backed short-term conversation memory with in-process fallback.
    Guarantees conversation continuity even when Redis is unavailable.
    """

    def __init__(self, settings: Settings) -> None:
        self._redis_url = settings.redis_url
        self._ttl = settings.memory_ttl_seconds
        self._max_turns = settings.memory_max_turns
        self._redis = None
        self._fallback: dict[str, ConversationHistory] = {}

    def _key(self, conversation_id: str) -> str:
        return f"brain:conv:{conversation_id}"

    def _user_key(self, user_id: str) -> str:
        return f"brain:user_convs:{user_id}"

    async def initialize(self) -> None:
        try:
            import redis.asyncio as aioredis
        except ImportError as exc:
            raise RuntimeError("redis package is required for conversation memory") from exc

        self._redis = aioredis.from_url(
            self._redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
        )
        try:
            await self._redis.ping()
            logger.info("Redis connected at %s", self._redis_url)
        except Exception:
            logger.warning("Redis not reachable at %s — memory will use in-process fallback", self._redis_url)
            self._redis = None

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()

    @property
    def is_connected(self) -> bool:
        return self._redis is not None

    @property
    def redis_client(self):
        """Expose the Redis client for shared use by other stores."""
        return self._redis

    async def get_or_create(self, user_id: str, conversation_id: str | None = None) -> ConversationHistory:
        if conversation_id:
            existing = await self._load(conversation_id)
            if existing:
                return existing

        conv_id = conversation_id or str(uuid.uuid4())
        history = ConversationHistory(
            conversation_id=conv_id,
            user_id=user_id,
        )
        await self._persist(history)
        return history

    async def add_turn(
        self, conversation_id: str, user_message: str, assistant_message: str
    ) -> ConversationHistory:
        history = await self._load(conversation_id)

        if not history:
            logger.warning(
                "Conversation %s not found — creating ephemeral entry to preserve turn",
                conversation_id,
            )
            history = ConversationHistory(conversation_id=conversation_id, user_id="unknown")

        history.messages.append(ChatMessage(role=MessageRole.USER, content=user_message))
        history.messages.append(ChatMessage(role=MessageRole.ASSISTANT, content=assistant_message))
        history.last_active = datetime.now(timezone.utc)

        if len(history.messages) > self._max_turns * 2:
            history.messages = history.messages[-(self._max_turns * 2):]

        await self._persist(history)
        return history

    async def get_history(self, conversation_id: str) -> list[ChatMessage]:
        history = await self._load(conversation_id)
        return history.messages if history else []

    async def get_status(self, conversation_id: str) -> MemoryStatusResponse | None:
        history = await self._load(conversation_id)
        if not history:
            return None

        ttl = None
        if self._redis:
            try:
                ttl = await self._redis.ttl(self._key(conversation_id))
                ttl = max(0, ttl)
            except Exception:
                pass

        return MemoryStatusResponse(
            conversation_id=conversation_id,
            turn_count=len(history.messages) // 2,
            ttl_remaining_seconds=ttl,
        )

    async def delete(self, conversation_id: str) -> bool:
        history = await self._load(conversation_id)
        if not history:
            return False

        if self._redis:
            try:
                await self._redis.srem(self._user_key(history.user_id), conversation_id)
                await self._redis.delete(self._key(conversation_id))
            except Exception:
                logger.warning("Redis delete failed for conversation %s", conversation_id)

        self._fallback.pop(conversation_id, None)
        return True

    async def _load(self, conversation_id: str) -> ConversationHistory | None:
        if self._redis:
            try:
                data = await self._redis.get(self._key(conversation_id))
                if data:
                    return ConversationHistory(**json.loads(data))
            except Exception:
                logger.warning("Redis read failed for conversation %s — checking fallback", conversation_id)

        return self._fallback.get(conversation_id)

    async def _persist(self, history: ConversationHistory) -> None:
        self._fallback[history.conversation_id] = history

        if self._redis:
            try:
                await self._redis.set(
                    self._key(history.conversation_id),
                    history.model_dump_json(),
                    ex=self._ttl,
                )
                await self._redis.sadd(self._user_key(history.user_id), history.conversation_id)
                await self._redis.expire(self._user_key(history.user_id), self._ttl)
            except Exception:
                logger.warning("Redis write failed for conversation %s — using fallback only", history.conversation_id)

    async def health_check(self) -> bool:
        if not self._redis:
            return False
        try:
            await self._redis.ping()
            return True
        except Exception:
            return False
