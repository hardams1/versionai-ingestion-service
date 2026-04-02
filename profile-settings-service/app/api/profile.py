from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.profile import UserProfile
from app.schemas.profile_schema import ProfileResponse, ProfileUpdateRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/profile", tags=["profile"])


async def _get_or_create_profile(db: AsyncSession, user: dict) -> UserProfile:
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user["user_id"])
    )
    profile = result.scalar_one_or_none()
    if not profile:
        profile = UserProfile(
            user_id=user["user_id"],
            username=user.get("username"),
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    return profile


@router.get("", response_model=ProfileResponse)
async def get_profile(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileResponse:
    profile = await _get_or_create_profile(db, user)
    return ProfileResponse(
        user_id=profile.user_id,
        username=profile.username,
        full_name=profile.full_name,
        email=profile.email,
        bio=profile.bio,
        image_url=profile.image_url,
        avatar_synced=profile.avatar_synced,
    )


@router.put("", response_model=ProfileResponse)
async def update_profile(
    body: ProfileUpdateRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileResponse:
    profile = await _get_or_create_profile(db, user)

    for key, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(profile, key, value)

    await db.commit()
    await db.refresh(profile)
    logger.info("Updated profile for user=%s", user["user_id"])

    return ProfileResponse(
        user_id=profile.user_id,
        username=profile.username,
        full_name=profile.full_name,
        email=profile.email,
        bio=profile.bio,
        image_url=profile.image_url,
        avatar_synced=profile.avatar_synced,
    )


@router.get("/{user_id}/public", response_model=ProfileResponse)
async def get_public_profile(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> ProfileResponse:
    """Public endpoint for sibling services to fetch user profile data."""
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        return ProfileResponse(user_id=user_id)
    return ProfileResponse(
        user_id=profile.user_id,
        username=profile.username,
        full_name=profile.full_name,
        image_url=profile.image_url,
        avatar_synced=profile.avatar_synced,
    )
