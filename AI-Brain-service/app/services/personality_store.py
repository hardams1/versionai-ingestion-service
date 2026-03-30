from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from app.models.schemas import PersonalityConfig

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


class PersonalityStore:
    """
    Redis-backed personality configuration store.
    Falls back to in-memory dict when Redis is unavailable.
    """

    def __init__(self, settings: Settings) -> None:
        self._redis = None
        self._fallback: dict[str, PersonalityConfig] = {}

    def _key(self, personality_id: str) -> str:
        return f"brain:personality:{personality_id}"

    def _user_key(self, user_id: str) -> str:
        return f"brain:user_personalities:{user_id}"

    async def initialize(self, redis_client=None) -> None:
        """Accept an external Redis client (shared with ConversationMemory)."""
        self._redis = redis_client
        if self._redis:
            logger.info("PersonalityStore using shared Redis connection")
        else:
            logger.warning("PersonalityStore running without Redis — using in-memory fallback")

    async def save(self, config: PersonalityConfig) -> PersonalityConfig:
        if self._redis:
            try:
                await self._redis.set(self._key(config.personality_id), config.model_dump_json())
                await self._redis.sadd(self._user_key(config.user_id), config.personality_id)
            except Exception:
                logger.warning("Redis write failed for personality %s — using fallback", config.personality_id)
                self._fallback[config.personality_id] = config
        else:
            self._fallback[config.personality_id] = config

        logger.info("Saved personality %s for user %s", config.personality_id, config.user_id)
        return config

    async def get(self, personality_id: str) -> PersonalityConfig | None:
        if self._redis:
            try:
                data = await self._redis.get(self._key(personality_id))
                if data:
                    return PersonalityConfig(**json.loads(data))
            except Exception:
                logger.warning("Redis read failed for personality %s — checking fallback", personality_id)

        return self._fallback.get(personality_id)

    async def list_for_user(self, user_id: str) -> list[PersonalityConfig]:
        if self._redis:
            try:
                ids = await self._redis.smembers(self._user_key(user_id))
                results: list[PersonalityConfig] = []
                for pid in ids:
                    config = await self.get(pid)
                    if config and config.user_id == user_id:
                        results.append(config)
                return results
            except Exception:
                logger.warning("Redis list failed for user %s — using fallback", user_id)

        return [p for p in self._fallback.values() if p.user_id == user_id]

    async def delete(self, personality_id: str) -> bool:
        config = await self.get(personality_id)

        if self._redis:
            try:
                if config:
                    await self._redis.srem(self._user_key(config.user_id), personality_id)
                result = await self._redis.delete(self._key(personality_id))
                self._fallback.pop(personality_id, None)
                return result > 0
            except Exception:
                logger.warning("Redis delete failed for personality %s", personality_id)

        return self._fallback.pop(personality_id, None) is not None
