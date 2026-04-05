from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx
import redis.asyncio as aioredis
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.category_stats import CategoryStats
from app.models.resolved_category import ResolvedCategory

logger = logging.getLogger(__name__)

NOTIFICATION_URL = "http://localhost:8013/api/v1/events/emit"


async def _emit_faq_event(owner_user_id: str, category: str, question_count: int) -> None:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(NOTIFICATION_URL, json={
                "event_type": "faq_category_updated",
                "user_id": owner_user_id,
                "payload": {"category": category, "question_count": question_count},
            })
    except Exception:
        logger.debug("Notification emit failed for faq_category_updated (non-critical)")


class RankingService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._redis: Optional[aioredis.Redis] = None
        self._ttl = settings.ranking_cache_ttl

    async def initialize(self) -> None:
        try:
            self._redis = aioredis.from_url(
                self._settings.redis_url, decode_responses=True
            )
            await self._redis.ping()
            logger.info("Redis connected for ranking cache")
        except Exception as exc:
            logger.warning("Redis unavailable, ranking will use DB only: %s", exc)
            self._redis = None

    async def close(self) -> None:
        if self._redis:
            await self._redis.close()

    async def increment_category(
        self, db: AsyncSession, owner_user_id: str, category: str
    ) -> None:
        result = await db.execute(
            select(CategoryStats).where(
                and_(
                    CategoryStats.owner_user_id == owner_user_id,
                    CategoryStats.category == category,
                )
            )
        )
        stats = result.scalar_one_or_none()

        if stats:
            stats.question_count += 1
            stats.last_updated = datetime.now(timezone.utc)
        else:
            stats = CategoryStats(
                owner_user_id=owner_user_id,
                category=category,
                question_count=1,
            )
            db.add(stats)

        await db.commit()
        await self._invalidate_cache(owner_user_id)
        count = stats.question_count
        asyncio.create_task(_emit_faq_event(owner_user_id, category, count))

    async def get_ranked_categories(
        self, db: AsyncSession, owner_user_id: str
    ) -> List[Dict]:
        cached = await self._get_from_cache(owner_user_id)
        if cached is not None:
            return cached

        resolved_q = select(ResolvedCategory.category).where(
            and_(
                ResolvedCategory.owner_user_id == owner_user_id,
                ResolvedCategory.status == "answered",
            )
        )
        resolved_result = await db.execute(resolved_q)
        suppressed = {row[0] for row in resolved_result.all()}

        stats_q = (
            select(CategoryStats)
            .where(CategoryStats.owner_user_id == owner_user_id)
            .order_by(CategoryStats.question_count.desc())
        )
        stats_result = await db.execute(stats_q)
        all_stats = stats_result.scalars().all()

        ranked = [
            {"category": s.category, "question_count": s.question_count}
            for s in all_stats
            if s.category not in suppressed
        ]

        await self._set_cache(owner_user_id, ranked)
        return ranked

    async def _get_from_cache(self, owner_user_id: str) -> Optional[List[Dict]]:
        if not self._redis:
            return None
        try:
            key = f"faq_rank:{owner_user_id}"
            data = await self._redis.get(key)
            if data:
                return json.loads(data)
        except Exception:
            pass
        return None

    async def _set_cache(self, owner_user_id: str, ranked: List[Dict]) -> None:
        if not self._redis:
            return
        try:
            key = f"faq_rank:{owner_user_id}"
            await self._redis.set(key, json.dumps(ranked), ex=self._ttl)
        except Exception:
            pass

    async def _invalidate_cache(self, owner_user_id: str) -> None:
        if not self._redis:
            return
        try:
            await self._redis.delete(f"faq_rank:{owner_user_id}")
        except Exception:
            pass
