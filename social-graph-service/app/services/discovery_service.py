from __future__ import annotations

import logging

from sqlalchemy import and_, or_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.follow import Follow
from app.models.social_profile import SocialProfile

logger = logging.getLogger(__name__)


async def search_users(db: AsyncSession, query: str, limit: int = 20, offset: int = 0):
    """Search users by username or full_name."""
    pattern = f"%{query}%"
    stmt = (
        select(SocialProfile)
        .where(
            or_(
                SocialProfile.username.ilike(pattern),
                SocialProfile.full_name.ilike(pattern),
            )
        )
        .order_by(SocialProfile.followers_count.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    profiles = result.scalars().all()

    count_stmt = select(func.count()).select_from(SocialProfile).where(
        or_(
            SocialProfile.username.ilike(pattern),
            SocialProfile.full_name.ilike(pattern),
        )
    )
    total = (await db.execute(count_stmt)).scalar() or 0
    return profiles, total


async def get_suggested_users(db: AsyncSession, user_id: str, limit: int = 20):
    """People followed by the user's followers (friends-of-friends)."""
    my_following = select(Follow.following_id).where(Follow.follower_id == user_id)

    friends_following = (
        select(Follow.following_id, func.count().label("score"))
        .where(
            and_(
                Follow.follower_id.in_(my_following),
                Follow.following_id != user_id,
                Follow.following_id.not_in(my_following),
            )
        )
        .group_by(Follow.following_id)
        .order_by(func.count().desc())
        .limit(limit)
    )
    result = await db.execute(friends_following)
    suggested_ids = [r[0] for r in result.all()]

    if not suggested_ids:
        fallback = (
            select(SocialProfile)
            .where(
                and_(
                    SocialProfile.user_id != user_id,
                    SocialProfile.user_id.not_in(my_following),
                    SocialProfile.ai_access_level == "public",
                )
            )
            .order_by(SocialProfile.followers_count.desc())
            .limit(limit)
        )
        result = await db.execute(fallback)
        return result.scalars().all()

    result = await db.execute(
        select(SocialProfile).where(SocialProfile.user_id.in_(suggested_ids))
    )
    return result.scalars().all()


async def get_trending_users(db: AsyncSession, limit: int = 20):
    """Most interacted AI profiles and highest follower counts."""
    stmt = (
        select(SocialProfile)
        .where(SocialProfile.ai_access_level != "no_one")
        .order_by(
            SocialProfile.ai_interaction_count.desc(),
            SocialProfile.followers_count.desc(),
        )
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()
