from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.core.security import get_current_user
from app.services.notification_service import (
    get_unread_count,
    get_user_notifications,
    mark_all_read,
    mark_read,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


class MarkReadRequest(BaseModel):
    notification_ids: list[str]


@router.get("", summary="List notifications for the authenticated user")
async def list_notifications(
    status: Optional[str] = Query(default=None, description="Filter: unread or read"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
) -> dict:
    items, total = await get_user_notifications(
        current_user["user_id"], status_filter=status, limit=limit, offset=offset,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/unread-count", summary="Get unread notification count by category")
async def unread_count(
    current_user: dict = Depends(get_current_user),
) -> dict:
    return await get_unread_count(current_user["user_id"])


@router.post("/mark-read", summary="Mark specific notifications as read")
async def mark_notifications_read(
    body: MarkReadRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    updated = await mark_read(current_user["user_id"], body.notification_ids)
    return {"updated": updated}


@router.post("/mark-all-read", summary="Mark all notifications as read")
async def mark_all_notifications_read(
    current_user: dict = Depends(get_current_user),
) -> dict:
    updated = await mark_all_read(current_user["user_id"])
    return {"updated": updated}
