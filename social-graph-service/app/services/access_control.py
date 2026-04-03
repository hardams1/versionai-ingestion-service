from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.follow_service import ensure_profile, is_following

logger = logging.getLogger(__name__)


async def check_ai_access(
    db: AsyncSession, requester_id: str, target_user_id: str,
) -> tuple:
    """Check whether requester can interact with target's AI.

    Returns (allowed: bool, reason: str).
    """
    if requester_id == target_user_id:
        return True, "Owner can always access their own AI"

    target = await ensure_profile(db, target_user_id)
    level = target.ai_access_level or "public"

    if level == "no_one":
        return False, "This user has disabled AI interactions"

    if level == "public":
        return True, "AI access is public"

    if level == "followers_only":
        follows = await is_following(db, requester_id, target_user_id)
        if follows:
            return True, "Requester is a follower"
        return False, "Only followers can interact with this user's AI"

    return False, f"Unknown access level: {level}"
