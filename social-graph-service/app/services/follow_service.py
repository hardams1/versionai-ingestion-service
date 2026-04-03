from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.follow import Follow
from app.models.follow_request import FollowRequest
from app.models.social_profile import SocialProfile

logger = logging.getLogger(__name__)


async def ensure_profile(db: AsyncSession, user_id: str, username: Optional[str] = None) -> SocialProfile:
    """Get or create a SocialProfile row for user_id."""
    result = await db.execute(select(SocialProfile).where(SocialProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        if username:
            existing = await db.execute(
                select(SocialProfile).where(SocialProfile.username == username)
            )
            if existing.scalar_one_or_none():
                username = None
        profile = SocialProfile(user_id=user_id, username=username)
        db.add(profile)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            profile = SocialProfile(user_id=user_id)
            db.add(profile)
            await db.commit()
        await db.refresh(profile)
    return profile


async def follow_user(db: AsyncSession, follower_id: str, target_id: str) -> dict:
    """Follow or send follow request depending on target's privacy setting."""
    if follower_id == target_id:
        return {"status": "error", "message": "Cannot follow yourself"}

    existing = await db.execute(
        select(Follow).where(
            and_(Follow.follower_id == follower_id, Follow.following_id == target_id)
        )
    )
    if existing.scalar_one_or_none():
        return {"status": "already_following", "message": "Already following this user"}

    target = await ensure_profile(db, target_id)

    if target.is_private:
        existing_req = await db.execute(
            select(FollowRequest).where(
                and_(
                    FollowRequest.requester_id == follower_id,
                    FollowRequest.target_id == target_id,
                    FollowRequest.status == "pending",
                )
            )
        )
        if existing_req.scalar_one_or_none():
            return {"status": "pending", "message": "Follow request already pending"}

        req = FollowRequest(requester_id=follower_id, target_id=target_id, status="pending")
        db.add(req)
        await db.commit()
        return {"status": "requested", "message": "Follow request sent"}

    return await _create_follow(db, follower_id, target_id)


async def unfollow_user(db: AsyncSession, follower_id: str, target_id: str) -> dict:
    result = await db.execute(
        select(Follow).where(
            and_(Follow.follower_id == follower_id, Follow.following_id == target_id)
        )
    )
    follow = result.scalar_one_or_none()
    if not follow:
        return {"status": "error", "message": "Not following this user"}

    await db.delete(follow)
    await _update_counts(db, follower_id, target_id, delta=-1)
    await db.commit()
    return {"status": "unfollowed", "message": "Unfollowed successfully"}


async def accept_request(db: AsyncSession, request_id: str, target_id: str) -> dict:
    result = await db.execute(
        select(FollowRequest).where(
            and_(FollowRequest.id == request_id, FollowRequest.target_id == target_id)
        )
    )
    req = result.scalar_one_or_none()
    if not req or req.status != "pending":
        return {"status": "error", "message": "Request not found or already handled"}

    req.status = "accepted"
    resp = await _create_follow(db, req.requester_id, req.target_id)
    await db.commit()
    return resp


async def reject_request(db: AsyncSession, request_id: str, target_id: str) -> dict:
    result = await db.execute(
        select(FollowRequest).where(
            and_(FollowRequest.id == request_id, FollowRequest.target_id == target_id)
        )
    )
    req = result.scalar_one_or_none()
    if not req or req.status != "pending":
        return {"status": "error", "message": "Request not found or already handled"}
    req.status = "rejected"
    await db.commit()
    return {"status": "rejected", "message": "Follow request rejected"}


async def get_followers(db: AsyncSession, user_id: str, limit: int = 50, offset: int = 0):
    count_q = await db.execute(select(func.count()).where(Follow.following_id == user_id))
    total = count_q.scalar() or 0

    result = await db.execute(
        select(Follow.follower_id)
        .where(Follow.following_id == user_id)
        .order_by(Follow.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    ids = [r[0] for r in result.all()]
    profiles = await _get_profiles_by_ids(db, ids)
    return profiles, total


async def get_following(db: AsyncSession, user_id: str, limit: int = 50, offset: int = 0):
    count_q = await db.execute(select(func.count()).where(Follow.follower_id == user_id))
    total = count_q.scalar() or 0

    result = await db.execute(
        select(Follow.following_id)
        .where(Follow.follower_id == user_id)
        .order_by(Follow.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    ids = [r[0] for r in result.all()]
    profiles = await _get_profiles_by_ids(db, ids)
    return profiles, total


async def get_pending_requests(db: AsyncSession, target_id: str):
    result = await db.execute(
        select(FollowRequest)
        .where(and_(FollowRequest.target_id == target_id, FollowRequest.status == "pending"))
        .order_by(FollowRequest.created_at.desc())
    )
    return result.scalars().all()


async def is_following(db: AsyncSession, follower_id: str, following_id: str) -> bool:
    result = await db.execute(
        select(Follow.id).where(
            and_(Follow.follower_id == follower_id, Follow.following_id == following_id)
        )
    )
    return result.scalar_one_or_none() is not None


async def has_pending_request(db: AsyncSession, requester_id: str, target_id: str) -> bool:
    result = await db.execute(
        select(FollowRequest.id).where(
            and_(
                FollowRequest.requester_id == requester_id,
                FollowRequest.target_id == target_id,
                FollowRequest.status == "pending",
            )
        )
    )
    return result.scalar_one_or_none() is not None


# ── helpers ──────────────────────────────────────────────────────────────────

async def _create_follow(db: AsyncSession, follower_id: str, following_id: str) -> dict:
    db.add(Follow(follower_id=follower_id, following_id=following_id))
    await _update_counts(db, follower_id, following_id, delta=1)
    await db.commit()
    return {"status": "following", "message": "Now following"}


async def _update_counts(db: AsyncSession, follower_id: str, following_id: str, delta: int):
    follower_profile = await ensure_profile(db, follower_id)
    following_profile = await ensure_profile(db, following_id)
    follower_profile.following_count = max(0, (follower_profile.following_count or 0) + delta)
    following_profile.followers_count = max(0, (following_profile.followers_count or 0) + delta)


async def _get_profiles_by_ids(db: AsyncSession, ids: list) -> list:
    if not ids:
        return []
    result = await db.execute(select(SocialProfile).where(SocialProfile.user_id.in_(ids)))
    profiles_map = {p.user_id: p for p in result.scalars().all()}
    return [profiles_map.get(uid) for uid in ids if profiles_map.get(uid)]
