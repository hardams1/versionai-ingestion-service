from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import UserSettings
from app.schemas.settings_schema import SettingsUpdateRequest

logger = logging.getLogger(__name__)


async def get_user_settings(db: AsyncSession, user_id: str) -> UserSettings:
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    settings = result.scalar_one_or_none()
    if not settings:
        settings = UserSettings(user_id=user_id)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
        logger.info("Created default settings for user=%s", user_id)
    return settings


async def update_user_settings(
    db: AsyncSession, user_id: str, update: SettingsUpdateRequest
) -> UserSettings:
    settings = await get_user_settings(db, user_id)

    update_data = update.model_dump(exclude_unset=True)
    if "notifications_enabled" in update_data:
        update_data["notifications_enabled"] = str(update_data["notifications_enabled"]).lower()

    for key, value in update_data.items():
        if value is not None:
            setattr(settings, key, value)

    await db.commit()
    await db.refresh(settings)
    logger.info("Updated settings for user=%s: %s", user_id, list(update_data.keys()))
    return settings
