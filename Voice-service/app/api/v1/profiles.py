from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends

from app.dependencies import get_voice_profile_service, verify_api_key
from app.models.schemas import VoiceProfileCreateRequest, VoiceProfileResponse
from app.services.voice_profile import VoiceProfileService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profiles", tags=["voice-profiles"])


@router.get(
    "/{user_id}",
    response_model=VoiceProfileResponse,
    summary="Get a user's voice profile",
)
async def get_profile(
    user_id: str,
    profile_svc: VoiceProfileService = Depends(get_voice_profile_service),
    _auth: None = Depends(verify_api_key),
) -> VoiceProfileResponse:
    profile = await profile_svc.resolve_voice(user_id)
    return VoiceProfileResponse(
        user_id=profile.user_id,
        voice_id=profile.voice_id,
        provider=profile.provider.value,
        display_name=profile.display_name,
    )


@router.post(
    "",
    response_model=VoiceProfileResponse,
    status_code=201,
    summary="Create or update a voice profile",
)
async def create_profile(
    request: VoiceProfileCreateRequest,
    profile_svc: VoiceProfileService = Depends(get_voice_profile_service),
    _auth: None = Depends(verify_api_key),
) -> VoiceProfileResponse:
    profile = await profile_svc.create_profile(
        user_id=request.user_id,
        voice_id=request.voice_id,
        provider=request.provider,
        display_name=request.display_name,
    )
    return VoiceProfileResponse(
        user_id=profile.user_id,
        voice_id=profile.voice_id,
        provider=profile.provider.value,
        display_name=profile.display_name,
    )


@router.delete(
    "/{user_id}",
    status_code=204,
    summary="Delete a user's voice profile",
)
async def delete_profile(
    user_id: str,
    profile_svc: VoiceProfileService = Depends(get_voice_profile_service),
    _auth: None = Depends(verify_api_key),
) -> None:
    await profile_svc.delete_profile(user_id)


@router.get(
    "",
    response_model=List[VoiceProfileResponse],
    summary="List all voice profiles",
)
async def list_profiles(
    profile_svc: VoiceProfileService = Depends(get_voice_profile_service),
    _auth: None = Depends(verify_api_key),
) -> list[VoiceProfileResponse]:
    profiles = await profile_svc.list_profiles()
    return [
        VoiceProfileResponse(
            user_id=p.user_id,
            voice_id=p.voice_id,
            provider=p.provider.value,
            display_name=p.display_name,
        )
        for p in profiles
    ]
