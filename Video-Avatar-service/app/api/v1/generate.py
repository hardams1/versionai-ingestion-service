from __future__ import annotations

import base64
import logging
import time
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.config import Settings, get_settings
from app.dependencies import get_avatar_profile_service, get_renderer, verify_api_key
from app.models.enums import GenerationStatus, RendererProvider, VideoFormat
from app.models.schemas import GenerateRequest, GenerateResponse
from app.services.avatar_profile import AvatarProfileService
from app.services.renderer import BaseRenderer
from app.utils.exceptions import (
    AudioTooLargeError,
    InvalidAudioError,
    MissingAudioInputError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generate", tags=["video-generation"])

VIDEO_CONTENT_TYPES = {
    VideoFormat.MP4: "video/mp4",
    VideoFormat.WEBM: "video/webm",
}


def _decode_audio(request: GenerateRequest, max_size: int) -> bytes:
    """Extract raw audio bytes from request, validating size."""
    if request.audio_base64:
        try:
            audio_data = base64.b64decode(request.audio_base64, validate=True)
        except Exception as exc:
            raise InvalidAudioError(f"Failed to decode base64 audio: {exc}") from exc
    elif request.audio_url:
        raise InvalidAudioError(
            "audio_url is reserved for future use; provide audio_base64 for now"
        )
    else:
        raise MissingAudioInputError()

    if len(audio_data) > max_size:
        raise AudioTooLargeError(len(audio_data), max_size)
    if len(audio_data) < 100:
        raise InvalidAudioError("Audio data too small to be valid")

    return audio_data


@router.post(
    "",
    response_model=GenerateResponse,
    summary="Validate generation parameters and preview",
    description=(
        "Resolves the user's avatar profile and validates the request "
        "without invoking the renderer. Use /generate/video to produce actual video."
    ),
)
async def generate_preview(
    request: GenerateRequest,
    settings: Settings = Depends(get_settings),
    renderer: BaseRenderer = Depends(get_renderer),
    profile_svc: AvatarProfileService = Depends(get_avatar_profile_service),
    _auth: None = Depends(verify_api_key),
) -> GenerateResponse:
    audio_data = _decode_audio(request, settings.max_audio_size_bytes)
    avatar = await profile_svc.resolve_avatar(request.user_id)
    resolution = request.resolution or settings.default_resolution
    fps = request.fps or settings.default_fps

    return GenerateResponse(
        generation_id=str(uuid.uuid4()),
        user_id=request.user_id,
        avatar_id=avatar.avatar_id,
        video_format=request.video_format,
        renderer_provider=RendererProvider(renderer.provider_name),
        resolution=resolution,
        fps=fps,
        duration_ms=0.0,
        video_duration_seconds=0.0,
        status=GenerationStatus.PENDING,
    )


@router.post(
    "/video",
    summary="Generate talking-face video from audio + avatar",
    description=(
        "Resolves the user's avatar profile, renders a lip-synced talking-face "
        "video using the configured renderer engine, and returns the video bytes."
    ),
)
async def generate_video(
    request: GenerateRequest,
    settings: Settings = Depends(get_settings),
    renderer: BaseRenderer = Depends(get_renderer),
    profile_svc: AvatarProfileService = Depends(get_avatar_profile_service),
    _auth: None = Depends(verify_api_key),
) -> StreamingResponse:
    audio_data = _decode_audio(request, settings.max_audio_size_bytes)
    avatar = await profile_svc.resolve_avatar(request.user_id)
    resolution = request.resolution or settings.default_resolution
    fps = request.fps or settings.default_fps
    content_type = VIDEO_CONTENT_TYPES.get(request.video_format, "video/mp4")

    logger.info(
        "Rendering video for user=%s avatar=%s provider=%s (%d audio bytes, res=%s, idle=%s)",
        request.user_id, avatar.avatar_id, renderer.provider_name,
        len(audio_data), resolution, request.idle_mode,
    )

    start = time.perf_counter()
    result = await renderer.render(
        audio_data=audio_data,
        avatar=avatar,
        video_format=request.video_format,
        resolution=resolution,
        fps=fps,
        idle_mode=request.idle_mode,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    logger.info(
        "Rendered %d bytes (%.1fs video) for user=%s avatar=%s in %.1fms",
        len(result.video_data), result.video_duration_seconds,
        request.user_id, avatar.avatar_id, elapsed_ms,
    )

    async def _yield_bytes():
        yield result.video_data

    return StreamingResponse(
        _yield_bytes(),
        media_type=content_type,
        headers={
            "Content-Length": str(len(result.video_data)),
            "X-Avatar-ID": avatar.avatar_id,
            "X-User-ID": request.user_id,
            "X-Video-Duration": f"{result.video_duration_seconds:.2f}",
            "X-Render-Time-Ms": f"{elapsed_ms:.1f}",
        },
    )
