from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)


async def generate_thumbnail(source_path: str, s3_key: str) -> str | None:
    """Generate a JPEG thumbnail for a video file. Returns the thumbnail path or None."""
    settings = get_settings()
    thumb_dir = Path(settings.thumbnails_dir)
    thumb_dir.mkdir(parents=True, exist_ok=True)

    safe_name = s3_key.replace("/", "_").rsplit(".", 1)[0] + ".jpg"
    thumb_path = thumb_dir / safe_name

    if thumb_path.exists():
        return str(thumb_path)

    src = Path(source_path)
    if not src.exists():
        return None

    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", str(src),
            "-ss", "00:00:01", "-vframes", "1",
            "-vf", "scale=320:-1",
            "-q:v", "5",
            str(thumb_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=15)
        if thumb_path.exists() and thumb_path.stat().st_size > 0:
            return str(thumb_path)
    except Exception:
        logger.debug("Thumbnail generation failed for %s", source_path, exc_info=True)

    return None


async def generate_text_preview(source_path: str) -> str | None:
    """Read the first ~500 chars of a text file for preview."""
    try:
        src = Path(source_path)
        if not src.exists():
            return None
        text = src.read_text(errors="replace")[:500]
        return text
    except Exception:
        return None
