from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.profile import UserProfile
from app.schemas.profile_schema import ImageUploadResponse
from app.services.image_service import ImageService
from app.integrations.video_avatar_client import VideoAvatarClient
from app.integrations.ai_brain_client import AIBrainClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/profile", tags=["upload"])


@router.post("/upload-image", response_model=ImageUploadResponse)
async def upload_profile_image(
    image: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ImageUploadResponse:
    img_svc = ImageService(settings)
    avatar_client = VideoAvatarClient(settings)
    brain_client = AIBrainClient(settings)

    if not image.content_type or not img_svc.validate_content_type(image.content_type):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid image type. Allowed: {settings.allowed_image_types}",
        )

    file_bytes = await image.read()
    if len(file_bytes) > settings.max_image_size_bytes:
        raise HTTPException(status_code=400, detail="Image too large (max 20MB)")
    if len(file_bytes) < 1000:
        raise HTTPException(status_code=400, detail="Image file too small")

    user_id = user["user_id"]

    image_url, storage_key = await img_svc.process_and_store(
        file_bytes, user_id, image.content_type
    )

    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        profile = UserProfile(user_id=user_id, username=user.get("username"))
        db.add(profile)

    profile.image_url = image_url
    profile.image_storage_key = storage_key
    await db.commit()
    await db.refresh(profile)

    avatar_synced = False
    image_b64 = img_svc.get_image_as_base64(user_id)
    if image_b64:
        avatar_synced = await avatar_client.sync_avatar(
            user_id, image_b64, profile.full_name
        )
        profile.avatar_synced = avatar_synced
        await db.commit()

    await brain_client.update_visual_profile(user_id, image_url)

    logger.info(
        "Profile image uploaded: user=%s url=%s avatar_synced=%s",
        user_id, image_url, avatar_synced,
    )

    return ImageUploadResponse(
        image_url=image_url,
        status="success",
        avatar_synced=avatar_synced,
    )
