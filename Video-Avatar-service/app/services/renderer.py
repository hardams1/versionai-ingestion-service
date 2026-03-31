from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import struct
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from app.config import Settings
from app.models.enums import VideoFormat
from app.models.schemas import AvatarProfile
from app.utils.exceptions import RendererProviderError

logger = logging.getLogger(__name__)


@dataclass
class RenderResult:
    video_data: bytes
    video_duration_seconds: float
    resolution: str
    fps: int


class BaseRenderer(ABC):
    """Abstract video renderer interface."""

    @abstractmethod
    async def render(
        self,
        audio_data: bytes,
        avatar: AvatarProfile,
        video_format: VideoFormat = VideoFormat.MP4,
        resolution: str = "512x512",
        fps: int = 25,
        idle_mode: bool = False,
    ) -> RenderResult:
        """Generate a talking-face video from audio + avatar profile."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider identifier."""


class SyncLabsRenderer(BaseRenderer):
    """Sync Labs API — high-fidelity lip-sync video generation.

    Flow: submit job → poll for completion → download result.
    """

    def __init__(self, settings: Settings) -> None:
        if not settings.synclabs_api_key:
            raise RendererProviderError("SYNCLABS_API_KEY is required for Sync Labs renderer")
        self._api_key = settings.synclabs_api_key
        self._base_url = settings.synclabs_api_url
        self._model = settings.synclabs_model
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"x-api-key": self._api_key, "Content-Type": "application/json"},
            timeout=httpx.Timeout(120.0, connect=15.0),
        )

    @property
    def provider_name(self) -> str:
        return "synclabs"

    async def render(
        self,
        audio_data: bytes,
        avatar: AvatarProfile,
        video_format: VideoFormat = VideoFormat.MP4,
        resolution: str = "512x512",
        fps: int = 25,
        idle_mode: bool = False,
    ) -> RenderResult:
        import base64

        payload = {
            "audioData": base64.b64encode(audio_data).decode(),
            "videoUrl": avatar.source_image_path,
            "model": self._model,
            "synergize": True,
            "output_format": video_format.value,
        }

        try:
            resp = await self._client.post("/lipsync", json=payload)
            resp.raise_for_status()
            job = resp.json()
            job_id = job["id"]
        except httpx.HTTPStatusError as exc:
            raise RendererProviderError(
                f"Sync Labs submission failed ({exc.response.status_code}): {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise RendererProviderError(f"Sync Labs request failed: {exc}") from exc

        video_bytes = await self._poll_job(job_id)

        return RenderResult(
            video_data=video_bytes,
            video_duration_seconds=len(audio_data) / 32000.0,
            resolution=resolution,
            fps=fps,
        )

    async def _poll_job(self, job_id: str, max_wait: float = 300.0, interval: float = 2.0) -> bytes:
        elapsed = 0.0
        while elapsed < max_wait:
            try:
                resp = await self._client.get(f"/lipsync/{job_id}")
                resp.raise_for_status()
                data = resp.json()
                status = data.get("status", "")

                if status == "COMPLETED":
                    video_url = data.get("videoUrl")
                    if not video_url:
                        raise RendererProviderError("Sync Labs completed but returned no videoUrl")
                    dl = await self._client.get(video_url)
                    dl.raise_for_status()
                    return dl.content

                if status == "FAILED":
                    raise RendererProviderError(f"Sync Labs job {job_id} failed: {data.get('error', 'unknown')}")

            except RendererProviderError:
                raise
            except Exception as exc:
                raise RendererProviderError(f"Error polling Sync Labs job: {exc}") from exc

            await asyncio.sleep(interval)
            elapsed += interval

        raise RendererProviderError(f"Sync Labs job {job_id} timed out after {max_wait}s")


class DIDRenderer(BaseRenderer):
    """D-ID API — talking head generation from a still image + audio."""

    def __init__(self, settings: Settings) -> None:
        if not settings.d_id_api_key:
            raise RendererProviderError("D_ID_API_KEY is required for D-ID renderer")
        self._api_key = settings.d_id_api_key
        self._base_url = settings.d_id_api_url
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Basic {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(120.0, connect=15.0),
        )

    @property
    def provider_name(self) -> str:
        return "d_id"

    async def render(
        self,
        audio_data: bytes,
        avatar: AvatarProfile,
        video_format: VideoFormat = VideoFormat.MP4,
        resolution: str = "512x512",
        fps: int = 25,
        idle_mode: bool = False,
    ) -> RenderResult:
        import base64

        payload = {
            "source_url": avatar.source_image_path,
            "script": {
                "type": "audio",
                "audio_url": f"data:audio/mp3;base64,{base64.b64encode(audio_data).decode()}",
            },
            "config": {"result_format": video_format.value},
        }

        try:
            resp = await self._client.post("/talks", json=payload)
            resp.raise_for_status()
            talk = resp.json()
            talk_id = talk["id"]
        except httpx.HTTPStatusError as exc:
            raise RendererProviderError(
                f"D-ID submission failed ({exc.response.status_code}): {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise RendererProviderError(f"D-ID request failed: {exc}") from exc

        video_bytes = await self._poll_talk(talk_id)

        return RenderResult(
            video_data=video_bytes,
            video_duration_seconds=len(audio_data) / 32000.0,
            resolution=resolution,
            fps=fps,
        )

    async def _poll_talk(self, talk_id: str, max_wait: float = 300.0, interval: float = 2.0) -> bytes:
        elapsed = 0.0
        while elapsed < max_wait:
            try:
                resp = await self._client.get(f"/talks/{talk_id}")
                resp.raise_for_status()
                data = resp.json()
                status = data.get("status", "")

                if status == "done":
                    result_url = data.get("result_url")
                    if not result_url:
                        raise RendererProviderError("D-ID completed but returned no result_url")
                    dl = await self._client.get(result_url)
                    dl.raise_for_status()
                    return dl.content

                if status in ("error", "rejected"):
                    raise RendererProviderError(f"D-ID talk {talk_id} failed: {data.get('error', 'unknown')}")

            except RendererProviderError:
                raise
            except Exception as exc:
                raise RendererProviderError(f"Error polling D-ID talk: {exc}") from exc

            await asyncio.sleep(interval)
            elapsed += interval

        raise RendererProviderError(f"D-ID talk {talk_id} timed out after {max_wait}s")


class MockRenderer(BaseRenderer):
    """Development/testing renderer that produces a minimal valid MP4.

    Deterministic: same audio + avatar → same output (hash-seeded).
    """

    @property
    def provider_name(self) -> str:
        return "mock"

    async def render(
        self,
        audio_data: bytes,
        avatar: AvatarProfile,
        video_format: VideoFormat = VideoFormat.MP4,
        resolution: str = "512x512",
        fps: int = 25,
        idle_mode: bool = False,
    ) -> RenderResult:
        duration = max(0.5, len(audio_data) / 32000.0)
        logger.info(
            "MockRenderer: generating %.1fs video for avatar=%s user=%s (%d audio bytes, idle=%s)",
            duration, avatar.avatar_id, avatar.user_id, len(audio_data), idle_mode,
        )
        await asyncio.sleep(0.05)

        fingerprint = hashlib.sha256(audio_data + avatar.avatar_id.encode()).digest()[:16]
        video_data = self._build_minimal_mp4(duration, resolution, fps, fingerprint)

        return RenderResult(
            video_data=video_data,
            video_duration_seconds=duration,
            resolution=resolution,
            fps=fps,
        )

    @staticmethod
    def _build_minimal_mp4(
        duration: float, resolution: str, fps: int, fingerprint: bytes
    ) -> bytes:
        """Build a minimal ISO BMFF (MP4) container.

        Not a playable video, but structurally valid enough for integration tests
        and size assertions. The fingerprint is embedded in mdat for determinism checks.
        """
        w, h = (int(x) for x in resolution.split("x"))
        num_frames = max(1, int(duration * fps))

        buf = io.BytesIO()

        # ftyp box
        ftyp_data = b"isom" + struct.pack(">I", 0x200) + b"isomiso2mp41"
        buf.write(struct.pack(">I", 8 + len(ftyp_data)))
        buf.write(b"ftyp")
        buf.write(ftyp_data)

        # mvhd box (108 bytes total)
        mvhd = io.BytesIO()
        mvhd.write(struct.pack(">I", 108))       # box size
        mvhd.write(b"mvhd")                       # box type
        mvhd.write(struct.pack(">I", 0))           # version + flags
        mvhd.write(struct.pack(">III", 0, 0, 1000))  # creation, modification, timescale
        mvhd.write(struct.pack(">I", int(duration * 1000)))  # duration
        mvhd.write(struct.pack(">I", 0x00010000))  # rate 1.0
        mvhd.write(struct.pack(">H", 0x0100))      # volume 1.0
        mvhd.write(b"\x00" * 10)                    # reserved
        mvhd.write(struct.pack(">9I",              # 3x3 matrix
            0x00010000, 0, 0,
            0, 0x00010000, 0,
            0, 0, 0x40000000,
        ))
        mvhd.write(b"\x00" * 24)                    # pre-defined
        mvhd.write(struct.pack(">I", 2))            # next_track_ID
        mvhd_bytes = mvhd.getvalue()

        # moov box wrapping mvhd
        buf.write(struct.pack(">I", 8 + len(mvhd_bytes)))
        buf.write(b"moov")
        buf.write(mvhd_bytes)

        # mdat box with deterministic payload
        frame_marker = fingerprint + struct.pack(">HHI", w, h, num_frames)
        mdat_payload = frame_marker * max(1, num_frames // 10 + 1)
        buf.write(struct.pack(">I", 8 + len(mdat_payload)))
        buf.write(b"mdat")
        buf.write(mdat_payload)

        return buf.getvalue()


def create_renderer(settings: Settings) -> BaseRenderer:
    """Factory — instantiate the configured renderer provider."""
    provider = settings.renderer_provider
    if provider == "synclabs":
        return SyncLabsRenderer(settings)
    elif provider == "d_id":
        return DIDRenderer(settings)
    elif provider == "mock":
        return MockRenderer()
    else:
        raise RendererProviderError(f"Unknown renderer provider: {provider}")
