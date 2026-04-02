from __future__ import annotations

import asyncio
import logging
import struct
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
        from pathlib import Path

        image_path = avatar.source_image_path
        if image_path and not image_path.startswith("mock://") and Path(image_path).is_file():
            img_bytes = Path(image_path).read_bytes()
            ext = Path(image_path).suffix.lower().lstrip(".")
            mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(ext, "image/jpeg")
            video_url = f"data:{mime};base64,{base64.b64encode(img_bytes).decode()}"
        else:
            video_url = avatar.source_image_path

        payload = {
            "audioData": base64.b64encode(audio_data).decode(),
            "videoUrl": video_url,
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
    """D-ID API — realistic lip-synced talking head from a still image + audio.

    Flow: upload image → create talk → poll for completion → download result.
    Local images are uploaded to D-ID's temporary storage first (24-48h TTL).
    """

    def __init__(self, settings: Settings) -> None:
        if not settings.d_id_api_key:
            raise RendererProviderError("D_ID_API_KEY is required for D-ID renderer")
        self._api_key = settings.d_id_api_key
        self._base_url = settings.d_id_api_url
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"Basic {self._api_key}"},
            timeout=httpx.Timeout(180.0, connect=15.0),
        )
        self._image_cache: dict[str, tuple[float, str]] = {}

    @property
    def provider_name(self) -> str:
        return "d_id"

    async def _upload_image(self, image_path: str) -> str:
        """Upload a local image to D-ID's /images endpoint.

        Cached per (path, mtime) so updated files trigger a re-upload.
        """
        import os
        from pathlib import Path

        p = Path(image_path)
        if not p.is_file():
            raise RendererProviderError(f"Avatar image not found: {image_path}")

        mtime = os.path.getmtime(image_path)
        cached = self._image_cache.get(image_path)
        if cached and cached[0] == mtime:
            logger.debug("D-ID: reusing cached image URL for %s", image_path)
            return cached[1]

        img_bytes = p.read_bytes()
        ext = p.suffix.lower().lstrip(".")
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(ext, "image/jpeg")
        filename = f"avatar.{ext}" if ext in ("jpg", "jpeg", "png") else "avatar.jpg"

        logger.info("D-ID: uploading image (%d bytes) from %s", len(img_bytes), image_path)

        try:
            resp = await self._client.post(
                "/images",
                files={"image": (filename, img_bytes, mime)},
            )
            resp.raise_for_status()
            data = resp.json()
            url = data.get("url")
            if not url:
                raise RendererProviderError(f"D-ID image upload returned no URL: {data}")
            logger.info("D-ID: image uploaded → %s", url[:80])
            self._image_cache[image_path] = (mtime, url)
            return url
        except httpx.HTTPStatusError as exc:
            raise RendererProviderError(
                f"D-ID image upload failed ({exc.response.status_code}): {exc.response.text[:300]}"
            ) from exc

    async def _upload_audio(self, audio_data: bytes) -> str:
        """Upload audio bytes to D-ID's /audios endpoint and return the hosted URL."""
        logger.info("D-ID: uploading audio (%d bytes)", len(audio_data))
        try:
            resp = await self._client.post(
                "/audios",
                files={"audio": ("speech.mp3", audio_data, "audio/mpeg")},
            )
            resp.raise_for_status()
            data = resp.json()
            url = data.get("url")
            if not url:
                raise RendererProviderError(f"D-ID audio upload returned no URL: {data}")
            duration = data.get("duration", 0)
            logger.info("D-ID: audio uploaded → %s (%.1fs)", url[:80], duration)
            return url
        except httpx.HTTPStatusError as exc:
            raise RendererProviderError(
                f"D-ID audio upload failed ({exc.response.status_code}): {exc.response.text[:300]}"
            ) from exc

    async def render(
        self,
        audio_data: bytes,
        avatar: AvatarProfile,
        video_format: VideoFormat = VideoFormat.MP4,
        resolution: str = "512x512",
        fps: int = 25,
        idle_mode: bool = False,
    ) -> RenderResult:
        image_path = avatar.source_image_path
        if not image_path or image_path.startswith("mock://"):
            raise RendererProviderError(
                "D-ID requires a real face photo. Upload a profile image first."
            )

        source_url = await self._upload_image(image_path)
        audio_url = await self._upload_audio(audio_data)

        payload = {
            "source_url": source_url,
            "script": {
                "type": "audio",
                "audio_url": audio_url,
            },
            "config": {
                "result_format": video_format.value,
                "stitch": True,
            },
        }

        logger.info(
            "D-ID: submitting talk for user=%s avatar=%s (%d audio bytes)",
            avatar.user_id, avatar.avatar_id, len(audio_data),
        )

        try:
            resp = await self._client.post(
                "/talks",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            talk = resp.json()
            talk_id = talk["id"]
            logger.info("D-ID: talk submitted, id=%s", talk_id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 402:
                raise RendererProviderError(
                    "D-ID: insufficient credits. Check your plan at https://www.d-id.com/"
                ) from exc
            raise RendererProviderError(
                f"D-ID submission failed ({exc.response.status_code}): {exc.response.text[:300]}"
            ) from exc
        except httpx.RequestError as exc:
            raise RendererProviderError(f"D-ID request failed: {exc}") from exc

        video_bytes, actual_duration = await self._poll_talk(talk_id)

        return RenderResult(
            video_data=video_bytes,
            video_duration_seconds=actual_duration,
            resolution=resolution,
            fps=fps,
        )

    async def _poll_talk(self, talk_id: str, max_wait: float = 300.0, interval: float = 3.0) -> tuple[bytes, float]:
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
                    logger.info("D-ID: talk %s done, downloading video", talk_id)
                    async with httpx.AsyncClient(timeout=60.0) as dl_client:
                        dl = await dl_client.get(result_url)
                        dl.raise_for_status()
                    duration = float(data.get("duration", 0) or 0)
                    return dl.content, duration

                if status in ("error", "rejected"):
                    error_info = data.get("error", data.get("reject_reason", "unknown"))
                    raise RendererProviderError(f"D-ID talk {talk_id} failed: {error_info}")

                if status == "started":
                    logger.debug("D-ID: talk %s processing (%.0fs elapsed)", talk_id, elapsed)

            except RendererProviderError:
                raise
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    logger.debug("D-ID: talk %s not ready yet", talk_id)
                else:
                    raise RendererProviderError(f"D-ID poll error: {exc}") from exc
            except Exception as exc:
                raise RendererProviderError(f"Error polling D-ID talk: {exc}") from exc

            await asyncio.sleep(interval)
            elapsed += interval

        raise RendererProviderError(f"D-ID talk {talk_id} timed out after {max_wait}s")


class MockRenderer(BaseRenderer):
    """Local renderer that produces real playable MP4 videos using FFmpeg.

    Combines the user's avatar image (or a generated placeholder) with audio
    into a proper H.264 + AAC MP4 that browsers can play natively.
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
        import shutil
        import tempfile
        from pathlib import Path

        w, h = (int(x) for x in resolution.split("x"))

        logger.info(
            "FFmpegRenderer: generating video for avatar=%s user=%s (%d audio bytes, res=%s)",
            avatar.avatar_id, avatar.user_id, len(audio_data), resolution,
        )

        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            raise RendererProviderError("ffmpeg not found on PATH")

        with tempfile.TemporaryDirectory(prefix="versionai_vid_") as tmpdir:
            tmp = Path(tmpdir)
            audio_file = tmp / "audio.mp3"
            image_file = tmp / "avatar.png"
            output_file = tmp / "output.mp4"

            audio_file.write_bytes(audio_data)

            image_path = avatar.source_image_path
            real_image = (
                image_path
                and not image_path.startswith("mock://")
                and Path(image_path).is_file()
            )

            if real_image:
                image_file = Path(image_path)
            else:
                self._generate_placeholder_image(image_file, w, h, avatar)

            cmd = [
                ffmpeg_bin, "-y",
                "-loop", "1",
                "-i", str(image_file),
                "-i", str(audio_file),
                "-c:v", "libx264",
                "-tune", "stillimage",
                "-c:a", "aac",
                "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black",
                "-r", str(fps),
                "-shortest",
                "-movflags", "+faststart",
                str(output_file),
            ]

            loop = asyncio.get_running_loop()
            proc = await loop.run_in_executor(None, lambda: __import__("subprocess").run(
                cmd, capture_output=True, timeout=120,
            ))

            if proc.returncode != 0:
                stderr = proc.stderr.decode(errors="replace")[-500:]
                raise RendererProviderError(f"ffmpeg failed (code {proc.returncode}): {stderr}")

            video_data = output_file.read_bytes()

            duration = await self._probe_duration(ffmpeg_bin, str(output_file), loop)

        logger.info(
            "FFmpegRenderer: produced %d bytes (%.1fs) for user=%s",
            len(video_data), duration, avatar.user_id,
        )

        return RenderResult(
            video_data=video_data,
            video_duration_seconds=duration,
            resolution=resolution,
            fps=fps,
        )

    @staticmethod
    async def _probe_duration(ffmpeg_bin: str, path: str, loop) -> float:
        ffprobe = ffmpeg_bin.replace("ffmpeg", "ffprobe")
        try:
            proc = await loop.run_in_executor(None, lambda: __import__("subprocess").run(
                [ffprobe, "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", path],
                capture_output=True, timeout=10,
            ))
            return float(proc.stdout.decode().strip())
        except Exception:
            return 0.0

    @staticmethod
    def _generate_placeholder_image(path, w: int, h: int, avatar: AvatarProfile) -> None:
        """Generate a simple placeholder PNG with the user's initial."""
        try:
            from PIL import Image, ImageDraw, ImageFont
            img = Image.new("RGB", (w, h), color=(30, 30, 30))
            draw = ImageDraw.Draw(img)

            initial = (avatar.display_name or avatar.user_id or "V")[0].upper()

            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size=int(h * 0.4))
            except Exception:
                font = ImageFont.load_default()

            bbox = draw.textbbox((0, 0), initial, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(((w - tw) / 2, (h - th) / 2 - bbox[1]), initial, fill=(200, 200, 200), font=font)

            draw.text(
                (w / 2, h - 30), "Upload a photo for your avatar",
                fill=(120, 120, 120), anchor="mm",
                font=ImageFont.load_default(),
            )
            img.save(str(path), "PNG")
        except ImportError:
            import struct as _struct
            _generate_minimal_png(path, w, h)


def _generate_minimal_png(path, w: int, h: int) -> None:
    """Fallback: write a solid dark-grey PNG without Pillow."""
    import zlib
    raw_row = b"\x00" + b"\x1e\x1e\x1e" * w
    raw = b"".join(raw_row for _ in range(h))
    compressed = zlib.compress(raw)

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        import struct as _s
        c = chunk_type + data
        return _s.pack(">I", len(data)) + c + _s.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", ihdr)
    png += _chunk(b"IDAT", compressed)
    png += _chunk(b"IEND", b"")
    path.write_bytes(png) if hasattr(path, "write_bytes") else open(str(path), "wb").write(png)


def create_renderer(settings: Settings) -> BaseRenderer:
    """Factory — instantiate the configured renderer provider.

    If set to 'auto', tries D-ID → SyncLabs → FFmpeg based on available keys.
    """
    provider = settings.renderer_provider

    if provider == "auto":
        if settings.d_id_api_key:
            logger.info("Auto-selected D-ID renderer (lip-sync enabled)")
            return DIDRenderer(settings)
        if settings.synclabs_api_key:
            logger.info("Auto-selected Sync Labs renderer (lip-sync enabled)")
            return SyncLabsRenderer(settings)
        logger.info("Auto-selected FFmpeg renderer (no lip-sync API keys found)")
        return MockRenderer()

    if provider == "d_id":
        return DIDRenderer(settings)
    elif provider == "synclabs":
        return SyncLabsRenderer(settings)
    elif provider == "mock":
        return MockRenderer()
    else:
        raise RendererProviderError(f"Unknown renderer provider: {provider}")
