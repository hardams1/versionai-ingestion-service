from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.schemas import (
    AnsweredFaqListResponse,
    FaqActionRequest,
    FaqActionResponse,
    FaqListResponse,
)

router = APIRouter(prefix="/faq", tags=["faq"])


def _get_faq_service():
    from app.main import faq_service
    return faq_service


@router.get("/list", response_model=FaqListResponse)
async def list_faqs(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    svc=Depends(_get_faq_service),
):
    return await svc.get_faq_list(db, user["user_id"])


@router.post("/action", response_model=FaqActionResponse)
async def faq_action(
    req: FaqActionRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    svc=Depends(_get_faq_service),
):
    return await svc.handle_action(db, user["user_id"], req)


@router.get("/answered", response_model=AnsweredFaqListResponse)
async def list_answered_faqs(
    owner_user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint for AI Brain to fetch answered FAQs for a user.

    No auth required — called internally by sibling services.
    """
    from app.main import faq_service
    return await faq_service.get_answered_faqs(db, owner_user_id)
