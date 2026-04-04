from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.schemas import (
    FollowRequestItem,
    FollowRequestListResponse,
    RequestAction,
)
from app.services.follow_service import (
    accept_request,
    get_pending_requests,
    reject_request,
)

router = APIRouter(prefix="/requests", tags=["follow-requests"])


@router.get("", response_model=FollowRequestListResponse)
async def list_pending_requests(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await get_pending_requests(db, user["user_id"])
    items = [
        FollowRequestItem(
            id=req.id,
            requester_id=req.requester_id,
            username=profile.username if profile else None,
            full_name=profile.full_name if profile else None,
            image_url=profile.image_url if profile else None,
            status=req.status,
            created_at=req.created_at.isoformat() if req.created_at else "",
        )
        for req, profile in rows
    ]
    return FollowRequestListResponse(items=items, total=len(items))


@router.post("/{request_id}")
async def handle_request(
    request_id: str,
    body: RequestAction,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.action == "accept":
        result = await accept_request(db, request_id, user["user_id"])
    else:
        result = await reject_request(db, request_id, user["user_id"])
    return result
