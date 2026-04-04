from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.question import Question
from app.models.schemas import CaptureRequest, CaptureResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])


def _get_categorization_service():
    from app.main import categorization_service
    return categorization_service


def _get_ranking_service():
    from app.main import ranking_service
    return ranking_service


async def _categorize_and_update(question_id: str, question_text: str, owner_user_id: str):
    """Background task: categorize the question and update stats."""
    from app.core.database import async_session
    from app.main import categorization_service, ranking_service

    category, confidence = await categorization_service.categorize(question_text)

    async with async_session() as db:
        from sqlalchemy import select
        from app.models.question import Question as Q
        result = await db.execute(select(Q).where(Q.id == question_id))
        q = result.scalar_one_or_none()
        if q:
            q.category = category
            q.confidence = confidence
            await db.commit()

        await ranking_service.increment_category(db, owner_user_id, category)

    logger.info(
        "Categorized question %s → '%s' (%.2f) for owner %s",
        question_id, category, confidence, owner_user_id,
    )


@router.post("/capture", response_model=CaptureResponse)
async def capture_question(
    req: CaptureRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    question = Question(
        owner_user_id=req.target_user_id,
        asker_user_id=req.asker_user_id,
        session_id=req.session_id,
        question_text=req.question,
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)

    background_tasks.add_task(
        _categorize_and_update,
        question.id,
        req.question,
        req.target_user_id,
    )

    return CaptureResponse(
        id=question.id,
        category=None,
        confidence=None,
        status="captured",
    )
