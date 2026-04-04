from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category_stats import CategoryStats
from app.models.question import Question
from app.models.resolved_category import ResolvedCategory
from app.models.schemas import (
    AnsweredFaqItem,
    AnsweredFaqListResponse,
    FaqActionRequest,
    FaqActionResponse,
    FaqCategoryItem,
    FaqListResponse,
)
from app.services.ranking_service import RankingService

logger = logging.getLogger(__name__)

SAMPLE_LIMIT = 5


class FaqService:
    def __init__(self, ranking: RankingService) -> None:
        self._ranking = ranking

    async def get_faq_list(
        self, db: AsyncSession, owner_user_id: str
    ) -> FaqListResponse:
        ranked = await self._ranking.get_ranked_categories(db, owner_user_id)

        items: list[FaqCategoryItem] = []
        for entry in ranked:
            category = entry["category"]
            samples_q = (
                select(Question.question_text)
                .where(
                    and_(
                        Question.owner_user_id == owner_user_id,
                        Question.category == category,
                    )
                )
                .order_by(Question.created_at.desc())
                .limit(SAMPLE_LIMIT)
            )
            result = await db.execute(samples_q)
            samples = [row[0] for row in result.all()]

            items.append(
                FaqCategoryItem(
                    category=category,
                    question_count=entry["question_count"],
                    sample_questions=samples,
                )
            )

        return FaqListResponse(items=items, total=len(items))

    async def handle_action(
        self,
        db: AsyncSession,
        owner_user_id: str,
        req: FaqActionRequest,
    ) -> FaqActionResponse:
        if req.action == "answer":
            return await self._answer_category(db, owner_user_id, req)
        else:
            return FaqActionResponse(
                category=req.category,
                action="skip",
                status="skipped",
            )

    async def _answer_category(
        self,
        db: AsyncSession,
        owner_user_id: str,
        req: FaqActionRequest,
    ) -> FaqActionResponse:
        existing = await db.execute(
            select(ResolvedCategory).where(
                and_(
                    ResolvedCategory.owner_user_id == owner_user_id,
                    ResolvedCategory.category == req.category,
                )
            )
        )
        resolved = existing.scalar_one_or_none()

        if resolved:
            resolved.answer_text = req.answer_text or resolved.answer_text
            resolved.status = "answered"
            resolved.resolved_at = datetime.now(timezone.utc)
        else:
            resolved = ResolvedCategory(
                owner_user_id=owner_user_id,
                category=req.category,
                answer_text=req.answer_text,
                status="answered",
            )
            db.add(resolved)

        await db.commit()
        await self._ranking._invalidate_cache(owner_user_id)

        logger.info(
            "Category '%s' answered by user %s — permanently suppressed",
            req.category,
            owner_user_id,
        )

        return FaqActionResponse(
            category=req.category,
            action="answer",
            status="resolved",
        )

    async def get_answered_faqs(
        self, db: AsyncSession, owner_user_id: str
    ) -> AnsweredFaqListResponse:
        result = await db.execute(
            select(ResolvedCategory).where(
                and_(
                    ResolvedCategory.owner_user_id == owner_user_id,
                    ResolvedCategory.status == "answered",
                    ResolvedCategory.answer_text.isnot(None),
                )
            )
        )
        rows = result.scalars().all()

        items = [
            AnsweredFaqItem(category=r.category, answer_text=r.answer_text or "")
            for r in rows
            if r.answer_text
        ]
        return AnsweredFaqListResponse(items=items, total=len(items))
