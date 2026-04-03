from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.schemas import DiscoveryResponse, SearchResult
from app.services.discovery_service import (
    get_suggested_users,
    get_trending_users,
    search_users,
)

router = APIRouter(prefix="/discover", tags=["discovery"])


def _profile_to_search_result(p) -> SearchResult:
    return SearchResult(
        user_id=p.user_id,
        username=p.username,
        full_name=p.full_name,
        bio=p.bio,
        image_url=p.image_url,
        followers_count=p.followers_count or 0,
        is_private=p.is_private or False,
        ai_access_level=p.ai_access_level or "public",
    )


@router.get("/search", response_model=DiscoveryResponse)
async def search(
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(default=20, le=50),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profiles, total = await search_users(db, q, limit, offset)
    return DiscoveryResponse(
        items=[_profile_to_search_result(p) for p in profiles],
        total=total,
    )


@router.get("/suggested", response_model=DiscoveryResponse)
async def suggested(
    limit: int = Query(default=20, le=50),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profiles = await get_suggested_users(db, user["user_id"], limit)
    return DiscoveryResponse(
        items=[_profile_to_search_result(p) for p in profiles],
        total=len(profiles),
    )


@router.get("/trending", response_model=DiscoveryResponse)
async def trending(
    limit: int = Query(default=20, le=50),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profiles = await get_trending_users(db, limit)
    return DiscoveryResponse(
        items=[_profile_to_search_result(p) for p in profiles],
        total=len(profiles),
    )
