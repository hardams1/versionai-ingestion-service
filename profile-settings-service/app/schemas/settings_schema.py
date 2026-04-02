from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class SettingsUpdateRequest(BaseModel):
    output_mode: Optional[Literal["chat", "voice", "video", "immersive"]] = None
    response_length: Optional[Literal["short", "medium", "long"]] = None
    creativity_level: Optional[Literal["low", "medium", "high"]] = None
    notifications_enabled: Optional[bool] = None
    voice_id: Optional[str] = None
    personality_intensity: Optional[Literal["subtle", "balanced", "strong"]] = None


class SettingsResponse(BaseModel):
    user_id: str
    output_mode: str = "chat"
    response_length: str = "medium"
    creativity_level: str = "medium"
    notifications_enabled: bool = True
    voice_id: Optional[str] = None
    personality_intensity: str = "balanced"

    model_config = {"from_attributes": True}
