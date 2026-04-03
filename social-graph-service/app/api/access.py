from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.schemas.schemas import AccessCheckRequest, AccessCheckResponse
from app.services.access_control import check_ai_access
from app.services.rate_limiter import check_rate_limit, get_remaining

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/access", tags=["access-control"])


@router.post("/check", response_model=AccessCheckResponse)
async def access_check(
    body: AccessCheckRequest,
    db: AsyncSession = Depends(get_db),
):
    """Check AI access permission AND rate limit in a single call.

    Used by the Orchestrator before routing to the Brain service.
    """
    allowed, reason = await check_ai_access(db, body.requester_id, body.target_user_id)
    if not allowed:
        return AccessCheckResponse(allowed=False, reason=reason, remaining_questions=0)

    try:
        redis = await get_redis()
    except Exception:
        redis = None

    rate_ok, remaining = await check_rate_limit(redis, body.requester_id, body.target_user_id)
    if not rate_ok:
        return AccessCheckResponse(
            allowed=False,
            reason="Daily interaction limit reached (5 questions per day per user)",
            remaining_questions=0,
        )

    return AccessCheckResponse(allowed=True, reason=reason, remaining_questions=remaining)
