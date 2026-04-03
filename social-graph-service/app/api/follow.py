from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.schemas import (
    FollowAction,
    FollowListResponse,
    FollowResponse,
    FollowerItem,
)
from app.services.follow_service import (
    ensure_profile,
    follow_user,
    get_followers,
    get_following,
    is_following,
    unfollow_user,
)

router = APIRouter(prefix="/follow", tags=["follow"])


@router.post("", response_model=FollowResponse)
async def follow(
    body: FollowAction,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_profile(db, user["user_id"], user.get("username"))
    result = await follow_user(db, user["user_id"], body.target_user_id)
    return FollowResponse(
        status=result["status"],
        message=result["message"],
        target_user_id=body.target_user_id,
    )


@router.post("/unfollow", response_model=FollowResponse)
async def unfollow(
    body: FollowAction,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await unfollow_user(db, user["user_id"], body.target_user_id)
    return FollowResponse(
        status=result["status"],
        message=result["message"],
        target_user_id=body.target_user_id,
    )


@router.get("/followers/{user_id}", response_model=FollowListResponse)
async def list_followers(
    user_id: str,
    limit: int = 50,
    offset: int = 0,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profiles, total = await get_followers(db, user_id, limit, offset)
    viewer_id = user["user_id"]
    items = []
    for p in profiles:
        mutual = await is_following(db, p.user_id, viewer_id) and await is_following(db, viewer_id, p.user_id)
        items.append(FollowerItem(
            user_id=p.user_id,
            username=p.username,
            full_name=p.full_name,
            image_url=p.image_url,
            is_mutual=mutual,
        ))
    return FollowListResponse(items=items, total=total)


@router.get("/following/{user_id}", response_model=FollowListResponse)
async def list_following(
    user_id: str,
    limit: int = 50,
    offset: int = 0,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profiles, total = await get_following(db, user_id, limit, offset)
    viewer_id = user["user_id"]
    items = []
    for p in profiles:
        mutual = await is_following(db, p.user_id, viewer_id) and await is_following(db, viewer_id, p.user_id)
        items.append(FollowerItem(
            user_id=p.user_id,
            username=p.username,
            full_name=p.full_name,
            image_url=p.image_url,
            is_mutual=mutual,
        ))
    return FollowListResponse(items=items, total=total)
