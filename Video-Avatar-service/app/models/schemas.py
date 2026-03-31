from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.models.enums import (
    AudioInputType,
    GenerationStatus,
    ImageFormat,
    ImageSourceType,
    RendererProvider,
    VideoFormat,
)


# ---------------------------------------------------------------------------
# Video generation request / response
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    user_id: str = Field(..., min_length=1, description="User whose avatar profile to use")
    audio_base64: str | None = Field(
        default=None,
        description="Base64-encoded audio bytes (provide this OR audio_url)",
    )
    audio_url: str | None = Field(
        default=None,
        description="URL to audio file (provide this OR audio_base64)",
    )
    video_format: VideoFormat = VideoFormat.MP4
    resolution: str | None = Field(default=None, description="WxH override, e.g. '1024x1024'")
    fps: int | None = Field(default=None, ge=1, le=60, description="Frames per second override")
    idle_mode: bool = Field(
        default=False,
        description="Generate idle animation (subtle movements, no speech) when True",
    )


class GenerateResponse(BaseModel):
    generation_id: str
    user_id: str
    avatar_id: str = Field(description="Resolved avatar profile identifier")
    video_format: VideoFormat
    renderer_provider: RendererProvider
    resolution: str
    fps: int
    duration_ms: float = Field(description="Processing wall-clock time in milliseconds")
    video_duration_seconds: float = Field(description="Duration of the output video")
    status: GenerationStatus
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Avatar profile (stored model)
# ---------------------------------------------------------------------------

class AvatarProfile(BaseModel):
    user_id: str
    avatar_id: str = Field(description="Unique avatar identifier")
    source_image_path: str = Field(description="Stored path to the validated face image")
    provider: RendererProvider
    display_name: str | None = None
    expression_baseline: str = Field(
        default="neutral",
        description="Default expression (neutral, smile, serious)",
    )
    image_width: int = Field(default=0, description="Validated source image width")
    image_height: int = Field(default=0, description="Validated source image height")
    image_format: str = Field(default="JPEG", description="Validated image format")
    image_source: ImageSourceType = Field(
        default=ImageSourceType.UPLOAD,
        description="Where the source image came from",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Avatar profile API schemas
# ---------------------------------------------------------------------------

class AvatarProfileResponse(BaseModel):
    user_id: str
    avatar_id: str
    source_image_path: str
    provider: str
    display_name: str | None = None
    expression_baseline: str
    image_width: int
    image_height: int
    image_format: str
    image_source: str


class AvatarProfileCreateRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    avatar_id: str = Field(..., min_length=1, description="Unique avatar identifier")
    source_image_base64: str = Field(
        ...,
        min_length=1,
        description="Base64-encoded photorealistic face image (JPEG or PNG)",
    )
    provider: RendererProvider = RendererProvider.MOCK
    display_name: str | None = None
    expression_baseline: str = Field(default="neutral")


class AvatarFromIngestionRequest(BaseModel):
    user_id: str = Field(..., min_length=1, description="User whose ingested data to use")
    avatar_id: str = Field(..., min_length=1, description="Unique avatar identifier")
    provider: RendererProvider = RendererProvider.MOCK
    display_name: str | None = None
    expression_baseline: str = Field(default="neutral")


# ---------------------------------------------------------------------------
# Health / Status
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    environment: str
    renderer_provider: str


class ErrorDetail(BaseModel):
    detail: str
    code: str | None = None
