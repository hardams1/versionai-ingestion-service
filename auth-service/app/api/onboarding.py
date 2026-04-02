from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.profile import Profile
from app.models.user import User
from app.schemas.profile_schema import OnboardingRequest, ProfileResponse
from app.services.auth_service import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("", response_model=ProfileResponse, status_code=201)
async def submit_onboarding(
    body: OnboardingRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Profile).where(Profile.user_id == user.id))
    profile = result.scalar_one_or_none()

    life_exp_parts = [
        body.life_experience.key_life_events,
        f"Career: {body.life_experience.career_background}" if body.life_experience.career_background else "",
        f"Education: {body.life_experience.education}" if body.life_experience.education else "",
    ]
    life_experiences_text = "\n\n".join(p for p in life_exp_parts if p)

    personality_traits = {
        "description": body.personality.description,
        "introvert_extrovert": body.personality.introvert_extrovert,
        "core_values": body.personality.core_values,
    }

    communication_style = {
        "formality": body.communication_style.formality,
        "uses_humor": body.communication_style.uses_humor,
        "emotional_response_style": body.communication_style.emotional_response_style,
    }

    beliefs = {
        "views_money": body.beliefs.views_money,
        "views_relationships": body.beliefs.views_relationships,
        "views_success": body.beliefs.views_success,
        "philosophical_beliefs": body.beliefs.philosophical_beliefs,
    }

    voice_tone = {
        "energy": body.voice_tone.energy,
        "response_length": body.voice_tone.response_length,
    }

    if profile:
        profile.full_name = body.basic_info.full_name
        profile.age = body.basic_info.age
        profile.gender = body.basic_info.gender
        profile.location = body.basic_info.location
        profile.personality_traits = personality_traits
        profile.communication_style = communication_style
        profile.beliefs = beliefs
        profile.voice_tone = voice_tone
        profile.life_experiences = life_experiences_text
    else:
        profile = Profile(
            user_id=user.id,
            full_name=body.basic_info.full_name,
            age=body.basic_info.age,
            gender=body.basic_info.gender,
            location=body.basic_info.location,
            personality_traits=personality_traits,
            communication_style=communication_style,
            beliefs=beliefs,
            voice_tone=voice_tone,
            life_experiences=life_experiences_text,
        )
        db.add(profile)

    user.onboarding_completed = True
    await db.commit()
    await db.refresh(profile)

    logger.info("Onboarding completed for user=%s (%s)", user.id, body.basic_info.full_name)

    return ProfileResponse(
        user_id=user.id,
        full_name=profile.full_name,
        age=profile.age,
        gender=profile.gender,
        location=profile.location,
        personality_traits=profile.personality_traits,
        communication_style=profile.communication_style,
        beliefs=profile.beliefs,
        voice_tone=profile.voice_tone,
        life_experiences=profile.life_experiences,
        onboarding_completed=True,
    )


@router.get("", response_model=ProfileResponse)
async def get_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Profile).where(Profile.user_id == user.id))
    profile = result.scalar_one_or_none()

    if not profile:
        return ProfileResponse(
            user_id=user.id,
            full_name=None,
            age=None,
            gender=None,
            location=None,
            personality_traits=None,
            communication_style=None,
            beliefs=None,
            voice_tone=None,
            life_experiences=None,
            onboarding_completed=user.onboarding_completed,
        )

    return ProfileResponse(
        user_id=user.id,
        full_name=profile.full_name,
        age=profile.age,
        gender=profile.gender,
        location=profile.location,
        personality_traits=profile.personality_traits,
        communication_style=profile.communication_style,
        beliefs=profile.beliefs,
        voice_tone=profile.voice_tone,
        life_experiences=profile.life_experiences,
        onboarding_completed=user.onboarding_completed,
    )


@router.get("/profile/{user_id}", response_model=ProfileResponse)
async def get_profile_by_user_id(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint for sibling services (Brain) to fetch onboarding data."""
    result = await db.execute(select(Profile).where(Profile.user_id == user_id))
    profile = result.scalar_one_or_none()

    if not profile:
        return ProfileResponse(
            user_id=user_id,
            full_name=None, age=None, gender=None, location=None,
            personality_traits=None, communication_style=None,
            beliefs=None, voice_tone=None, life_experiences=None,
            onboarding_completed=False,
        )

    return ProfileResponse(
        user_id=user_id,
        full_name=profile.full_name,
        age=profile.age,
        gender=profile.gender,
        location=profile.location,
        personality_traits=profile.personality_traits,
        communication_style=profile.communication_style,
        beliefs=profile.beliefs,
        voice_tone=profile.voice_tone,
        life_experiences=profile.life_experiences,
        onboarding_completed=True,
    )
