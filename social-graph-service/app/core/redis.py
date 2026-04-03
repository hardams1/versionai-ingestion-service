from __future__ import annotations

import logging
from typing import Optional

import redis.asyncio as aioredis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_pool: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
        )
        try:
            await _pool.ping()
            logger.info("Redis connected at %s", settings.redis_url)
        except Exception as exc:
            logger.warning("Redis unavailable (%s) — rate limiting will be disabled", exc)
            _pool = None
            raise
    return _pool


async def close_redis():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
