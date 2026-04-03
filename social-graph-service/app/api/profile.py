from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.social_profile import SocialProfile
from app.schemas.schemas import ProfileResponse, ProfileUpdate
from app.services.follow_service import (
    ensure_profile,
    has_pending_request,
    is_following,
)

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await ensure_profile(db, user["user_id"], user.get("username"))
    return _to_response(profile, is_own=True)


@router.put("/me", response_model=ProfileResponse)
async def update_my_profile(
    body: ProfileUpdate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await ensure_profile(db, user["user_id"], user.get("username"))

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)
    return _to_response(profile, is_own=True)


@router.get("/{user_id}", response_model=ProfileResponse)
async def get_user_profile(
    user_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await ensure_profile(db, user_id)
    viewer_id = user["user_id"]

    i_follow = await is_following(db, viewer_id, user_id)
    they_follow = await is_following(db, user_id, viewer_id)
    pending = await has_pending_request(db, viewer_id, user_id) if not i_follow else False

    return ProfileResponse(
        user_id=profile.user_id,
        username=profile.username,
        full_name=profile.full_name,
        bio=profile.bio,
        image_url=profile.image_url,
        is_private=profile.is_private,
        ai_access_level=profile.ai_access_level,
        followers_count=profile.followers_count or 0,
        following_count=profile.following_count or 0,
        is_following=i_follow,
        is_follower=they_follow,
        is_mutual=i_follow and they_follow,
        follow_request_pending=pending,
    )


@router.get("/{user_id}/public")
async def get_public_profile(user_id: str, db: AsyncSession = Depends(get_db)):
    """Unauthenticated endpoint for sibling services."""
    profile = await ensure_profile(db, user_id)
    return {
        "user_id": profile.user_id,
        "username": profile.username,
        "is_private": profile.is_private,
        "ai_access_level": profile.ai_access_level,
        "followers_count": profile.followers_count or 0,
    }


def _to_response(profile: SocialProfile, is_own: bool = False) -> ProfileResponse:
    return ProfileResponse(
        user_id=profile.user_id,
        username=profile.username,
        full_name=profile.full_name,
        bio=profile.bio,
        image_url=profile.image_url,
        is_private=profile.is_private,
        ai_access_level=profile.ai_access_level,
        followers_count=profile.followers_count or 0,
        following_count=profile.following_count or 0,
        is_following=False,
        is_follower=False,
        is_mutual=False,
        follow_request_pending=False,
    )
