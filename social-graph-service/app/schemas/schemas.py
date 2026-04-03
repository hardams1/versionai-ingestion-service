from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ── Profile ──────────────────────────────────────────────────────────────────

class ProfileResponse(BaseModel):
    user_id: str
    username: Optional[str] = None
    full_name: Optional[str] = None
    bio: Optional[str] = None
    image_url: Optional[str] = None
    is_private: bool = False
    ai_access_level: str = "public"
    followers_count: int = 0
    following_count: int = 0
    is_following: bool = False
    is_follower: bool = False
    is_mutual: bool = False
    follow_request_pending: bool = False


class ProfileUpdate(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None
    bio: Optional[str] = None
    image_url: Optional[str] = None
    phone_number: Optional[str] = None
    is_private: Optional[bool] = None
    ai_access_level: Optional[Literal["public", "followers_only", "no_one"]] = None


# ── Follow ───────────────────────────────────────────────────────────────────

class FollowAction(BaseModel):
    target_user_id: str = Field(..., min_length=1)


class FollowResponse(BaseModel):
    status: str
    message: str
    target_user_id: str


class FollowerItem(BaseModel):
    user_id: str
    username: Optional[str] = None
    full_name: Optional[str] = None
    image_url: Optional[str] = None
    is_mutual: bool = False


class FollowListResponse(BaseModel):
    items: List[FollowerItem]
    total: int


# ── Follow Requests ──────────────────────────────────────────────────────────

class RequestAction(BaseModel):
    action: Literal["accept", "reject"]


class FollowRequestItem(BaseModel):
    id: str
    requester_id: str
    username: Optional[str] = None
    full_name: Optional[str] = None
    image_url: Optional[str] = None
    status: str
    created_at: str


class FollowRequestListResponse(BaseModel):
    items: List[FollowRequestItem]
    total: int


# ── Access Control ───────────────────────────────────────────────────────────

class AccessCheckRequest(BaseModel):
    requester_id: str = Field(..., min_length=1)
    target_user_id: str = Field(..., min_length=1)


class AccessCheckResponse(BaseModel):
    allowed: bool
    reason: str
    remaining_questions: Optional[int] = None


# ── Discovery ────────────────────────────────────────────────────────────────

class SearchResult(BaseModel):
    user_id: str
    username: Optional[str] = None
    full_name: Optional[str] = None
    bio: Optional[str] = None
    image_url: Optional[str] = None
    followers_count: int = 0
    is_private: bool = False
    ai_access_level: str = "public"


class DiscoveryResponse(BaseModel):
    items: List[SearchResult]
    total: int
