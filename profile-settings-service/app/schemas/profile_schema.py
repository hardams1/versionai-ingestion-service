from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    bio: Optional[str] = None


class ProfileResponse(BaseModel):
    user_id: str
    username: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    bio: Optional[str] = None
    image_url: Optional[str] = None
    avatar_synced: bool = False

    model_config = {"from_attributes": True}


class ImageUploadResponse(BaseModel):
    image_url: str
    status: str = "success"
    avatar_synced: bool = False
