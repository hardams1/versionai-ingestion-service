from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_orchestrator, verify_api_key
from app.models.schemas import ChatRequest, ChatResponse
from app.services.orchestrator import BrainOrchestrator

router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(verify_api_key)])


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    orchestrator: BrainOrchestrator = Depends(get_orchestrator),
) -> ChatResponse:
    """
    Send a query grounded in the user's uploaded documents.

    The pipeline: embed query → retrieve context → build prompt → LLM → safety check → respond.
    """
    return await orchestrator.chat(request)
