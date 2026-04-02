from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.settings_schema import SettingsResponse, SettingsUpdateRequest
from app.services.settings_service import get_user_settings, update_user_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])


def _to_response(s) -> SettingsResponse:
    return SettingsResponse(
        user_id=s.user_id,
        output_mode=s.output_mode,
        response_length=s.response_length,
        creativity_level=s.creativity_level,
        notifications_enabled=s.notifications_enabled == "true",
        voice_id=s.voice_id,
        personality_intensity=s.personality_intensity or "balanced",
    )


@router.get("", response_model=SettingsResponse)
async def get_settings_endpoint(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SettingsResponse:
    settings = await get_user_settings(db, user["user_id"])
    return _to_response(settings)


@router.post("/update", response_model=SettingsResponse)
async def update_settings_endpoint(
    body: SettingsUpdateRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SettingsResponse:
    settings = await update_user_settings(db, user["user_id"], body)
    logger.info("Settings updated for user=%s", user["user_id"])
    return _to_response(settings)


@router.get("/{user_id}/public", response_model=SettingsResponse)
async def get_public_settings(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> SettingsResponse:
    """Public endpoint for orchestrator to fetch user output_mode."""
    settings = await get_user_settings(db, user_id)
    return _to_response(settings)
