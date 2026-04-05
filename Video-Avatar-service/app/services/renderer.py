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
    """D-ID API — realistic lip-synced talking head from image or video source + audio.

    Prefers calibration video as source_url when available (natural head motion,
    blinking, micro-expressions) — this single change eliminates the "talking picture"
    problem. Falls back to still image when no calibration video exists.

    Flow: upload source → create talk → poll for completion → download result.
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
        self._source_cache: dict[str, tuple[float, str]] = {}

    @property
    def provider_name(self) -> str:
        return "d_id"

    async def _upload_source(self, file_path: str, is_video: bool = False) -> str:
        """Upload a local image or video to D-ID's temporary storage.

        Cached per (path, mtime) so updated files trigger a re-upload.
        """
        import os
        from pathlib import Path

        p = Path(file_path)
        if not p.is_file():
            raise RendererProviderError(f"Source file not found: {file_path}")

        mtime = os.path.getmtime(file_path)
        cached = self._source_cache.get(file_path)
        if cached and cached[0] == mtime:
            logger.debug("D-ID: reusing cached source URL for %s", file_path)
            return cached[1]

        file_bytes = p.read_bytes()
        ext = p.suffix.lower().lstrip(".")

        if is_video:
            mime = {"mp4": "video/mp4", "webm": "video/webm", "mov": "video/quicktime"}.get(ext, "video/mp4")
            filename = f"calibration.{ext}"
            endpoint = "/clips"
        else:
            mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(ext, "image/jpeg")
            filename = f"avatar.{ext}" if ext in ("jpg", "jpeg", "png") else "avatar.jpg"
            endpoint = "/images"

        logger.info(
            "D-ID: uploading %s (%d bytes) from %s",
            "video" if is_video else "image", len(file_bytes), file_path,
        )

        try:
            field_name = "clip" if is_video else "image"
            resp = await self._client.post(
                endpoint,
                files={field_name: (filename, file_bytes, mime)},
            )
            resp.raise_for_status()
            data = resp.json()
            url = data.get("url")
            if not url:
                raise RendererProviderError(f"D-ID upload returned no URL: {data}")
            logger.info("D-ID: source uploaded → %s", url[:80])
            self._source_cache[file_path] = (mtime, url)
            return url
        except httpx.HTTPStatusError as exc:
            raise RendererProviderError(
                f"D-ID source upload failed ({exc.response.status_code}): {exc.response.text[:300]}"
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
        from pathlib import Path

        image_path = avatar.source_image_path
        if not image_path or image_path.startswith("mock://"):
            raise RendererProviderError(
                "D-ID requires a real face photo. Upload a profile image first."
            )

        use_video_source = (
            avatar.has_calibration_video
            and avatar.calibration_video_path
            and Path(avatar.calibration_video_path).is_file()
        )

        if use_video_source:
            logger.info(
                "D-ID: using calibration VIDEO as source for user=%s (enhanced realism)",
                avatar.user_id,
            )
            source_url = await self._upload_source(avatar.calibration_video_path, is_video=True)
        else:
            logger.info("D-ID: using still IMAGE as source for user=%s", avatar.user_id)
            source_url = await self._upload_source(image_path, is_video=False)

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
            "D-ID: submitting talk for user=%s avatar=%s (%d audio bytes, source=%s)",
            avatar.user_id, avatar.avatar_id, len(audio_data),
            "video" if use_video_source else "image",
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


class HeyGenRenderer(BaseRenderer):
    """HeyGen API — studio-quality avatar from video source + audio.

    HeyGen produces the highest-quality results when given a calibration video
    rather than a still image. It handles lip-sync, head motion, and expression
    transfer internally using their proprietary neural rendering pipeline.

    Flow: create video → poll for completion → download result.
    """

    def __init__(self, settings: Settings) -> None:
        if not settings.heygen_api_key:
            raise RendererProviderError("HEYGEN_API_KEY is required for HeyGen renderer")
        self._api_key = settings.heygen_api_key
        self._base_url = settings.heygen_api_url
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "X-Api-Key": self._api_key,
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(300.0, connect=15.0),
        )

    @property
    def provider_name(self) -> str:
        return "heygen"

    async def _upload_asset(self, file_path: str) -> str:
        """Upload a local video/image to HeyGen's asset storage."""
        from pathlib import Path

        p = Path(file_path)
        if not p.is_file():
            raise RendererProviderError(f"Asset file not found: {file_path}")

        file_bytes = p.read_bytes()
        ext = p.suffix.lower().lstrip(".")
        mime_map = {
            "mp4": "video/mp4", "webm": "video/webm", "mov": "video/quicktime",
            "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
        }
        mime = mime_map.get(ext, "application/octet-stream")

        logger.info("HeyGen: uploading asset (%d bytes) from %s", len(file_bytes), file_path)

        try:
            resp = await self._client.post(
                "/v1/asset",
                files={"file": (p.name, file_bytes, mime)},
                headers={"X-Api-Key": self._api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            asset_id = data.get("data", {}).get("asset_id")
            if not asset_id:
                raise RendererProviderError(f"HeyGen upload returned no asset_id: {data}")
            logger.info("HeyGen: asset uploaded → %s", asset_id)
            return asset_id
        except httpx.HTTPStatusError as exc:
            raise RendererProviderError(
                f"HeyGen upload failed ({exc.response.status_code}): {exc.response.text[:300]}"
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
        import base64
        import tempfile
        from pathlib import Path

        has_video = (
            avatar.has_calibration_video
            and avatar.calibration_video_path
            and Path(avatar.calibration_video_path).is_file()
        )

        if has_video:
            logger.info("HeyGen: using calibration video for user=%s", avatar.user_id)
            source_path = avatar.calibration_video_path
        else:
            source_path = avatar.source_image_path
            if not source_path or source_path.startswith("mock://"):
                raise RendererProviderError(
                    "HeyGen requires a face photo or calibration video."
                )

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_audio:
            tmp_audio.write(audio_data)
            tmp_audio_path = tmp_audio.name

        try:
            audio_asset_id = await self._upload_asset(tmp_audio_path)
            source_asset_id = await self._upload_asset(source_path)

            payload = {
                "video_inputs": [{
                    "character": {
                        "type": "talking_photo" if not has_video else "avatar",
                        "talking_photo_id" if not has_video else "avatar_id": source_asset_id,
                    },
                    "voice": {
                        "type": "audio",
                        "audio_asset_id": audio_asset_id,
                    },
                }],
                "dimension": {
                    "width": int(resolution.split("x")[0]),
                    "height": int(resolution.split("x")[1]),
                },
            }

            resp = await self._client.post("/v2/video/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()
            video_id = data.get("data", {}).get("video_id")
            if not video_id:
                raise RendererProviderError(f"HeyGen returned no video_id: {data}")

            logger.info("HeyGen: video generation started, id=%s", video_id)

            video_bytes, duration = await self._poll_video(video_id)

            return RenderResult(
                video_data=video_bytes,
                video_duration_seconds=duration,
                resolution=resolution,
                fps=fps,
            )
        except RendererProviderError:
            raise
        except httpx.HTTPStatusError as exc:
            raise RendererProviderError(
                f"HeyGen generation failed ({exc.response.status_code}): {exc.response.text[:300]}"
            ) from exc
        finally:
            Path(tmp_audio_path).unlink(missing_ok=True)

    async def _poll_video(self, video_id: str, max_wait: float = 600.0, interval: float = 5.0) -> tuple[bytes, float]:
        elapsed = 0.0
        while elapsed < max_wait:
            try:
                resp = await self._client.get(f"/v1/video_status.get?video_id={video_id}")
                resp.raise_for_status()
                data = resp.json().get("data", {})
                status = data.get("status", "")

                if status == "completed":
                    video_url = data.get("video_url")
                    if not video_url:
                        raise RendererProviderError("HeyGen completed but no video_url")
                    logger.info("HeyGen: video %s complete, downloading", video_id)
                    async with httpx.AsyncClient(timeout=120.0) as dl_client:
                        dl = await dl_client.get(video_url)
                        dl.raise_for_status()
                    duration = float(data.get("duration", 0) or 0)
                    return dl.content, duration

                if status == "failed":
                    error = data.get("error", {}).get("message", "unknown")
                    raise RendererProviderError(f"HeyGen video {video_id} failed: {error}")

                logger.debug("HeyGen: video %s status=%s (%.0fs)", video_id, status, elapsed)

            except RendererProviderError:
                raise
            except Exception as exc:
                raise RendererProviderError(f"HeyGen poll error: {exc}") from exc

            await asyncio.sleep(interval)
            elapsed += interval

        raise RendererProviderError(f"HeyGen video {video_id} timed out after {max_wait}s")


class MockRenderer(BaseRenderer):
    """Local renderer using FFmpeg. When a calibration video is available,
    overlays the audio onto the real video (preserving natural motion) instead
    of looping a still image — a dramatic quality improvement at zero API cost.
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

        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            raise RendererProviderError("ffmpeg not found on PATH")

        has_calibration_video = (
            avatar.has_calibration_video
            and avatar.calibration_video_path
            and Path(avatar.calibration_video_path).is_file()
        )

        logger.info(
            "FFmpegRenderer: generating video for user=%s (%d audio bytes, source=%s)",
            avatar.user_id, len(audio_data),
            "calibration_video" if has_calibration_video else "still_image",
        )

        with tempfile.TemporaryDirectory(prefix="versionai_vid_") as tmpdir:
            tmp = Path(tmpdir)
            audio_file = tmp / "audio.mp3"
            output_file = tmp / "output.mp4"
            audio_file.write_bytes(audio_data)

            if has_calibration_video:
                cmd = self._build_video_source_cmd(
                    ffmpeg_bin, avatar.calibration_video_path,
                    str(audio_file), str(output_file), w, h, fps,
                )
            else:
                image_file = tmp / "avatar.png"
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

                cmd = self._build_image_source_cmd(
                    ffmpeg_bin, str(image_file), str(audio_file),
                    str(output_file), w, h, fps,
                )

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
    def _build_video_source_cmd(
        ffmpeg_bin: str, video_path: str, audio_path: str,
        output_path: str, w: int, h: int, fps: int,
    ) -> list[str]:
        """FFmpeg command that replaces calibration video audio with TTS audio,
        keeping the original video's natural head motion and expressions."""
        return [
            ffmpeg_bin, "-y",
            "-stream_loop", "-1",
            "-i", video_path,
            "-i", audio_path,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black",
            "-r", str(fps),
            "-shortest",
            "-movflags", "+faststart",
            output_path,
        ]

    @staticmethod
    def _build_image_source_cmd(
        ffmpeg_bin: str, image_path: str, audio_path: str,
        output_path: str, w: int, h: int, fps: int,
    ) -> list[str]:
        return [
            ffmpeg_bin, "-y",
            "-loop", "1",
            "-i", image_path,
            "-i", audio_path,
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black",
            "-r", str(fps),
            "-shortest",
            "-movflags", "+faststart",
            output_path,
        ]

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

    If set to 'auto', tries HeyGen → D-ID → SyncLabs → FFmpeg based on available keys.
    HeyGen is preferred because it produces the highest quality with video source input.
    """
    provider = settings.renderer_provider

    if provider == "auto":
        if settings.heygen_api_key:
            logger.info("Auto-selected HeyGen renderer (studio-quality avatar)")
            return HeyGenRenderer(settings)
        if settings.d_id_api_key:
            logger.info("Auto-selected D-ID renderer (lip-sync enabled)")
            return DIDRenderer(settings)
        if settings.synclabs_api_key:
            logger.info("Auto-selected Sync Labs renderer (lip-sync enabled)")
            return SyncLabsRenderer(settings)
        logger.info("Auto-selected FFmpeg renderer (no lip-sync API keys found)")
        return MockRenderer()

    if provider == "heygen":
        return HeyGenRenderer(settings)
    elif provider == "d_id":
        return DIDRenderer(settings)
    elif provider == "synclabs":
        return SyncLabsRenderer(settings)
    elif provider == "mock":
        return MockRenderer()
    else:
        raise RendererProviderError(f"Unknown renderer provider: {provider}")
