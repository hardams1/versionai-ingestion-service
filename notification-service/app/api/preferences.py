from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.models.notification import NotificationPreferences
from app.services.notification_service import get_preferences, update_preferences

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("", summary="Get notification preferences")
async def get_user_preferences(
    current_user: dict = Depends(get_current_user),
) -> dict:
    return await get_preferences(current_user["user_id"])


@router.put("", summary="Update notification preferences")
async def update_user_preferences(
    prefs: NotificationPreferences,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return await update_preferences(current_user["user_id"], prefs.model_dump())
