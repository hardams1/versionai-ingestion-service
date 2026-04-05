from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Platform = Literal["twitter", "facebook", "instagram", "tiktok", "snapchat"]
ContentType = Literal["post", "comment", "like", "reply", "share", "story"]


class ConnectRequest(BaseModel):
    platform: Platform
    access_token: str = Field(..., min_length=1)
    refresh_token: Optional[str] = None
    platform_user_id: Optional[str] = None
    platform_username: Optional[str] = None
    scopes: Optional[str] = None


class ConnectResponse(BaseModel):
    id: str
    platform: str
    platform_username: Optional[str] = None
    status: str
    connected_at: str


class OAuthInitResponse(BaseModel):
    authorization_url: str
    state: str


class OAuthCallbackRequest(BaseModel):
    platform: Platform
    code: str
    state: str


class AccountStatusResponse(BaseModel):
    platform: str
    is_connected: bool
    platform_username: Optional[str] = None
    connected_at: Optional[str] = None
    last_sync_at: Optional[str] = None
    items_ingested: int = 0


class AllAccountsResponse(BaseModel):
    accounts: List[AccountStatusResponse]


class SyncResponse(BaseModel):
    platform: str
    status: str
    items_ingested: int
    message: str


class DisconnectResponse(BaseModel):
    platform: str
    status: str
    message: str


class DeleteDataResponse(BaseModel):
    platform: str
    items_deleted: int
    status: str


class NormalizedContent(BaseModel):
    user_id: str
    platform: str
    type: ContentType
    content: str
    topics: List[str] = Field(default_factory=list)
    hashtags: List[str] = Field(default_factory=list)
    mentions: List[str] = Field(default_factory=list)
    engagement_score: float = 0.0
    timestamp: str


class IngestionStats(BaseModel):
    total_items: int
    by_platform: dict
    by_type: dict
    last_sync: Optional[str] = None
