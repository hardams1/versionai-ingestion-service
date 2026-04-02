from __future__ import annotations

from pydantic import BaseModel, Field


class BasicInfo(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=200)
    age: int | None = Field(default=None, ge=1, le=150)
    gender: str | None = Field(default=None, max_length=50)
    location: str | None = Field(default=None, max_length=200)


class PersonalityInfo(BaseModel):
    description: str = Field(default="", max_length=2000)
    introvert_extrovert: str = Field(default="", max_length=100)
    core_values: str = Field(default="", max_length=2000)


class CommunicationStyle(BaseModel):
    formality: str = Field(default="", max_length=100)
    uses_humor: bool = False
    emotional_response_style: str = Field(default="", max_length=2000)


class LifeExperience(BaseModel):
    key_life_events: str = Field(default="", max_length=5000)
    career_background: str = Field(default="", max_length=2000)
    education: str = Field(default="", max_length=2000)


class BeliefsPreferences(BaseModel):
    views_money: str = Field(default="", max_length=2000)
    views_relationships: str = Field(default="", max_length=2000)
    views_success: str = Field(default="", max_length=2000)
    philosophical_beliefs: str = Field(default="", max_length=2000)


class VoiceTone(BaseModel):
    energy: str = Field(default="", max_length=100)
    response_length: str = Field(default="", max_length=100)


class OnboardingRequest(BaseModel):
    basic_info: BasicInfo
    personality: PersonalityInfo
    communication_style: CommunicationStyle
    life_experience: LifeExperience
    beliefs: BeliefsPreferences
    voice_tone: VoiceTone


class ProfileResponse(BaseModel):
    user_id: str
    full_name: str | None
    age: int | None
    gender: str | None
    location: str | None
    personality_traits: dict | None
    communication_style: dict | None
    beliefs: dict | None
    voice_tone: dict | None
    life_experiences: str | None
    onboarding_completed: bool
