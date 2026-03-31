from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends

from app.dependencies import (
    get_avatar_profile_service,
    get_ingestion_client,
    verify_api_key,
)
from app.models.enums import ImageSourceType
from app.models.schemas import (
    AvatarFromIngestionRequest,
    AvatarProfileCreateRequest,
    AvatarProfileResponse,
)
from app.services.avatar_profile import AvatarProfileService
from app.services.ingestion_client import IngestionClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/avatars", tags=["avatar-profiles"])


def _profile_to_response(p) -> AvatarProfileResponse:
    return AvatarProfileResponse(
        user_id=p.user_id,
        avatar_id=p.avatar_id,
        source_image_path=p.source_image_path,
        provider=p.provider.value,
        display_name=p.display_name,
        expression_baseline=p.expression_baseline,
        image_width=p.image_width,
        image_height=p.image_height,
        image_format=p.image_format,
        image_source=p.image_source.value if hasattr(p.image_source, "value") else p.image_source,
    )


@router.get(
    "/{user_id}",
    response_model=AvatarProfileResponse,
    summary="Get a user's avatar profile",
)
async def get_avatar(
    user_id: str,
    profile_svc: AvatarProfileService = Depends(get_avatar_profile_service),
    _auth: None = Depends(verify_api_key),
) -> AvatarProfileResponse:
    profile = await profile_svc.resolve_avatar(user_id)
    return _profile_to_response(profile)


@router.post(
    "",
    response_model=AvatarProfileResponse,
    status_code=201,
    summary="Create avatar from a photorealistic face image",
    description=(
        "Upload a base64-encoded photorealistic face image (JPEG or PNG) to "
        "create an avatar profile. The image is validated for format, resolution "
        "(min 256x256), color mode (RGB), and aspect ratio before being stored."
    ),
)
async def create_avatar(
    request: AvatarProfileCreateRequest,
    profile_svc: AvatarProfileService = Depends(get_avatar_profile_service),
    _auth: None = Depends(verify_api_key),
) -> AvatarProfileResponse:
    profile = await profile_svc.create_from_base64(
        user_id=request.user_id,
        avatar_id=request.avatar_id,
        image_base64=request.source_image_base64,
        provider=request.provider,
        display_name=request.display_name,
        expression_baseline=request.expression_baseline,
    )
    return _profile_to_response(profile)


@router.post(
    "/from-ingestion",
    response_model=AvatarProfileResponse,
    status_code=201,
    summary="Auto-create avatar from user's ingested data",
    description=(
        "Fetches the user's best face image from the ingestion pipeline (Microservice #1), "
        "validates it for photorealistic quality, and creates an avatar profile. "
        "The image must have been previously uploaded through the ingestion service."
    ),
)
async def create_avatar_from_ingestion(
    request: AvatarFromIngestionRequest,
    profile_svc: AvatarProfileService = Depends(get_avatar_profile_service),
    ingestion: IngestionClient = Depends(get_ingestion_client),
    _auth: None = Depends(verify_api_key),
) -> AvatarProfileResponse:
    ingested = await ingestion.fetch_user_face_image(request.user_id)
    logger.info(
        "Fetched ingested image for user=%s: %s (%d bytes)",
        request.user_id, ingested.s3_key, ingested.size_bytes,
    )

    profile = await profile_svc.create_profile(
        user_id=request.user_id,
        avatar_id=request.avatar_id,
        image_bytes=ingested.image_bytes,
        provider=request.provider,
        display_name=request.display_name,
        expression_baseline=request.expression_baseline,
        image_source=ImageSourceType.INGESTION,
    )
    return _profile_to_response(profile)


@router.delete(
    "/{user_id}",
    status_code=204,
    summary="Delete a user's avatar profile and stored face image",
)
async def delete_avatar(
    user_id: str,
    profile_svc: AvatarProfileService = Depends(get_avatar_profile_service),
    _auth: None = Depends(verify_api_key),
) -> None:
    await profile_svc.delete_profile(user_id)


@router.get(
    "",
    response_model=List[AvatarProfileResponse],
    summary="List all avatar profiles",
)
async def list_avatars(
    profile_svc: AvatarProfileService = Depends(get_avatar_profile_service),
    _auth: None = Depends(verify_api_key),
) -> list[AvatarProfileResponse]:
    profiles = await profile_svc.list_profiles()
    return [_profile_to_response(p) for p in profiles]
