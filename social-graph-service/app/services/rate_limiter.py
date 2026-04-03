from __future__ import annotations

import logging
from typing import Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def check_rate_limit(
    redis_client, requester_id: str, target_user_id: str,
) -> tuple:
    """Check and increment the rate limit counter.

    Returns (allowed: bool, remaining: int).
    """
    settings = get_settings()
    max_q = settings.rate_limit_max_questions
    window = settings.rate_limit_window_seconds

    if requester_id == target_user_id:
        return True, max_q

    if redis_client is None:
        logger.warning("Redis unavailable — rate limiting disabled")
        return True, max_q

    key = f"rate:{requester_id}:{target_user_id}"

    try:
        current = await redis_client.get(key)
        count = int(current) if current else 0

        if count >= max_q:
            return False, 0

        pipe = redis_client.pipeline()
        pipe.incr(key)
        if count == 0:
            pipe.expire(key, window)
        await pipe.execute()

        remaining = max_q - count - 1
        return True, remaining

    except Exception as exc:
        logger.error("Rate limit check failed: %s", exc)
        return True, max_q


async def get_remaining(
    redis_client, requester_id: str, target_user_id: str,
) -> int:
    settings = get_settings()
    if redis_client is None:
        return settings.rate_limit_max_questions

    key = f"rate:{requester_id}:{target_user_id}"
    try:
        current = await redis_client.get(key)
        count = int(current) if current else 0
        return max(0, settings.rate_limit_max_questions - count)
    except Exception:
        return settings.rate_limit_max_questions
