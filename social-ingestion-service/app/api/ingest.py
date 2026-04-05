from __future__ import annotations

import json
import logging
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.integrations.registry import SUPPORTED_PLATFORMS
from app.models.schemas import IngestionStats, SyncResponse
from app.models.social_content import SocialContent
from app.services.ingestion_service import get_ingestion_stats, sync_platform
from app.services.normalization_service import extract_hashtags, extract_mentions, extract_topics
from app.services.pipeline_service import push_to_embedding_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingestion"])


class ManualContentItem(BaseModel):
    content: str = Field(..., min_length=1)
    content_type: str = "post"
    platform: str = "manual"
    engagement_score: float = 0.0


class ManualIngestRequest(BaseModel):
    items: List[ManualContentItem] = Field(..., min_items=1)


class ManualIngestResponse(BaseModel):
    items_stored: int
    items_embedded: int
    topics_found: List[str]
    message: str


async def _bg_sync_and_embed(user_id: str, platform: str):
    """Background task: sync platform data then push to embedding pipeline."""
    from app.core.database import async_session

    async with async_session() as db:
        try:
            await sync_platform(db, user_id, platform)
        except Exception as exc:
            logger.error("Background sync failed for %s/%s: %s", user_id, platform, exc)
            return

    try:
        await push_to_embedding_pipeline(user_id, platform)
    except Exception as exc:
        logger.error("Background embed failed for %s/%s: %s", user_id, platform, exc)


@router.post("/sync/{platform}", response_model=SyncResponse)
async def trigger_sync(
    platform: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger an immediate sync for a platform."""
    if platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {platform}")

    try:
        new_items = await sync_platform(db, user["user_id"], platform)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    background_tasks.add_task(push_to_embedding_pipeline, user["user_id"], platform)

    return SyncResponse(
        platform=platform,
        status="synced",
        items_ingested=new_items,
        message=f"Synced {new_items} new items from {platform.title()}",
    )


@router.post("/sync-all")
async def trigger_sync_all(
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger sync for all connected platforms."""
    from app.services.ingestion_service import get_user_accounts

    accounts = await get_user_accounts(db, user["user_id"])
    active = [a for a in accounts if a.is_active]

    if not active:
        return {"status": "no_accounts", "message": "No connected accounts to sync"}

    for account in active:
        background_tasks.add_task(_bg_sync_and_embed, user["user_id"], account.platform)

    return {
        "status": "syncing",
        "platforms": [a.platform for a in active],
        "message": f"Syncing {len(active)} platform(s) in background",
    }


@router.post("/manual", response_model=ManualIngestResponse)
async def manual_ingest(
    req: ManualIngestRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually ingest content (for testing or direct data entry).

    Accepts a list of content items, runs topic extraction, stores them,
    then pushes to the embedding pipeline in the background.
    """
    user_id = user["user_id"]
    all_topics: set = set()
    stored = 0

    for item in req.items:
        topics = extract_topics(item.content)
        hashtags = extract_hashtags(item.content)
        mentions = extract_mentions(item.content)
        all_topics.update(topics)

        content = SocialContent(
            user_id=user_id,
            platform=item.platform,
            content_type=item.content_type,
            content_text=item.content,
            topics=json.dumps(topics),
            hashtags=json.dumps(hashtags),
            mentions=json.dumps(mentions),
            engagement_score=item.engagement_score,
        )
        db.add(content)
        stored += 1

    await db.commit()
    logger.info("Manual ingest: stored %d items for user %s", stored, user_id)

    platforms = {item.platform for item in req.items}
    for platform in platforms:
        background_tasks.add_task(push_to_embedding_pipeline, user_id, platform)

    return ManualIngestResponse(
        items_stored=stored,
        items_embedded=0,
        topics_found=sorted(all_topics),
        message=f"Stored {stored} items. Embedding pipeline triggered in background.",
    )


@router.get("/stats", response_model=IngestionStats)
async def stats(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get ingestion statistics for the current user."""
    data = await get_ingestion_stats(db, user["user_id"])
    return IngestionStats(**data)
