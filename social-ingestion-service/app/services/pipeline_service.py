from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import httpx
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.social_content import SocialContent
from app.services.normalization_service import compute_writing_style

logger = logging.getLogger(__name__)

NOTIFICATION_URL = "http://localhost:8013/api/v1/events/emit"


async def _emit_ai_event(event_type: str, user_id: str, platform: str, count: int) -> None:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(NOTIFICATION_URL, json={
                "event_type": event_type,
                "user_id": user_id,
                "payload": {"source": "social", "platform": platform, "items_count": count},
                "idempotency_key": f"{event_type}-{user_id}-{platform}-{datetime.now(timezone.utc).strftime('%Y%m%d%H')}",
            })
    except Exception:
        logger.debug("Notification emit failed for %s (non-critical)", event_type)

INGESTION_STORAGE_DIR = Path(__file__).resolve().parents[3] / "ingestion-service" / "storage"


async def push_to_embedding_pipeline(user_id: str, platform: str) -> int:
    """Send un-embedded content to the Processing-Embedding service.

    Opens its own DB session so it can safely run as a background task.
    """
    from app.core.database import async_session

    async with async_session() as db:
        return await _push_to_embedding(db, user_id, platform)


async def _push_to_embedding(db: AsyncSession, user_id: str, platform: str) -> int:
    settings = get_settings()

    result = await db.execute(
        select(SocialContent).where(
            and_(
                SocialContent.user_id == user_id,
                SocialContent.platform == platform,
                SocialContent.embedded == 0,
                SocialContent.content_text.isnot(None),
            )
        )
    )
    items = result.scalars().all()
    if not items:
        logger.info("No un-embedded content for %s/%s", user_id, platform)
        return 0

    combined_text = _build_social_document(items, platform)
    text_bytes = combined_text.encode("utf-8")
    checksum = hashlib.sha256(text_bytes).hexdigest()
    unique_id = uuid.uuid4().hex[:12]
    filename = f"social_{platform}_{unique_id}.txt"

    s3_key = f"uploads/text/{datetime.now(timezone.utc).strftime('%Y/%m/%d')}/{unique_id}_{filename}"

    file_path = INGESTION_STORAGE_DIR / s3_key
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(text_bytes)
        logger.info("Wrote social content file: %s (%d bytes)", file_path, len(text_bytes))
    except Exception as exc:
        logger.error("Failed to write social content file: %s", exc)
        return 0

    queue_message = {
        "ingestion_id": f"social-{user_id}-{platform}-{unique_id}",
        "filename": filename,
        "s3_bucket": "versionai-ingestion",
        "s3_key": s3_key,
        "file_category": "text",
        "mime_type": "text/plain",
        "size_bytes": len(text_bytes),
        "checksum_sha256": checksum,
        "pipelines": ["embedding"],
        "metadata": {
            "source": "social-ingestion",
            "platform": platform,
            "user_id": user_id,
            "items_count": len(items),
        },
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.processing_service_url}/api/v1/process",
                json=queue_message,
            )
            if resp.status_code in (200, 202):
                for item in items:
                    item.embedded = 1
                await db.commit()
                asyncio.create_task(_emit_ai_event("ai_personality_updated", user_id, platform, len(items)))
                logger.info(
                    "Pushed %d %s items to embedding pipeline for user %s (status=%d)",
                    len(items), platform, user_id, resp.status_code,
                )
                return len(items)
            else:
                logger.warning(
                    "Processing service returned %d: %s",
                    resp.status_code, resp.text[:300],
                )
    except Exception as exc:
        logger.error("Failed to push to embedding pipeline: %s", exc)

    return 0


def _build_social_document(items: List[SocialContent], platform: str) -> str:
    """Build a single text document from social content for embedding."""
    sections = []
    sections.append(f"=== Social Media Content from {platform.title()} ===\n")

    texts = [item.content_text for item in items if item.content_text]
    style = compute_writing_style(texts)
    sections.append(
        f"Writing style: {style['formality']}, "
        f"avg post length: {style['avg_length']} chars, "
        f"emoji usage: {style['emoji_usage']}\n"
    )

    all_topics = set()
    for item in items:
        if item.topics:
            try:
                all_topics.update(json.loads(item.topics))
            except (json.JSONDecodeError, TypeError):
                pass

    if all_topics:
        sections.append(f"Topics engaged with: {', '.join(sorted(all_topics))}\n")

    sections.append("--- Posts and Content ---\n")

    sorted_items = sorted(
        items,
        key=lambda x: x.engagement_score or 0,
        reverse=True,
    )

    for item in sorted_items:
        if not item.content_text:
            continue
        line = f"[{item.content_type}] {item.content_text}"
        if item.engagement_score and item.engagement_score > 0:
            line += f" (engagement: {item.engagement_score})"
        sections.append(line)

    return "\n".join(sections)
