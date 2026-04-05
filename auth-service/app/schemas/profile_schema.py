from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class BasicInfo(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=200)
    age: int = Field(..., ge=1, le=150)
    gender: str = Field(..., min_length=1, max_length=50)
    location: str = Field(..., min_length=1, max_length=200)

    @field_validator("age", mode="before")
    @classmethod
    def coerce_age(cls, v):  # noqa: N805
        if v is None or v == "" or v == "null":
            return None
        return v


class PersonalityInfo(BaseModel):
    description: str = Field(..., min_length=1, max_length=2000)
    introvert_extrovert: str = Field(..., min_length=1, max_length=100)
    core_values: str = Field(..., min_length=1, max_length=2000)


class CommunicationStyle(BaseModel):
    formality: str = Field(..., min_length=1, max_length=100)
    uses_humor: bool = False
    emotional_response_style: str = Field(..., min_length=1, max_length=2000)


class LifeExperience(BaseModel):
    key_life_events: str = Field(..., min_length=1, max_length=5000)
    career_background: str = Field(..., min_length=1, max_length=2000)
    education: str = Field(..., min_length=1, max_length=2000)


class BeliefsPreferences(BaseModel):
    views_money: str = Field(..., min_length=1, max_length=2000)
    views_relationships: str = Field(..., min_length=1, max_length=2000)
    views_success: str = Field(..., min_length=1, max_length=2000)
    philosophical_beliefs: str = Field(..., min_length=1, max_length=2000)


class VoiceTone(BaseModel):
    energy: str = Field(..., min_length=1, max_length=100)
    response_length: str = Field(..., min_length=1, max_length=100)


class OnboardingRequest(BaseModel):
    basic_info: BasicInfo
    personality: PersonalityInfo
    communication_style: CommunicationStyle
    life_experience: LifeExperience
    beliefs: BeliefsPreferences
    voice_tone: VoiceTone


class ProfileResponse(BaseModel):
    user_id: str
    full_name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    location: Optional[str] = None
    personality_traits: Optional[dict] = None
    communication_style: Optional[dict] = None
    beliefs: Optional[dict] = None
    voice_tone: Optional[dict] = None
    life_experiences: Optional[str] = None
    onboarding_completed: bool
