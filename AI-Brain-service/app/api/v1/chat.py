from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_memory, get_orchestrator, verify_api_key
from app.models.schemas import ChatMessage, ChatRequest, ChatResponse
from app.services.memory import ConversationMemory
from app.services.orchestrator import BrainOrchestrator

router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(verify_api_key)])


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    orchestrator: BrainOrchestrator = Depends(get_orchestrator),
) -> ChatResponse:
    """
    Send a query grounded in the user's uploaded documents.

    The pipeline: embed query → retrieve context → build identity → build prompt → LLM → safety check → respond.
    """
    return await orchestrator.chat(request)


@router.get("/history/{conversation_id}", response_model=List[ChatMessage])
async def get_chat_history(
    conversation_id: str,
    memory: ConversationMemory = Depends(get_memory),
) -> list[ChatMessage]:
    """Retrieve the full message history for a conversation."""
    messages = await memory.get_history(conversation_id)
    if not messages:
        raise HTTPException(status_code=404, detail="Conversation not found or empty")
    return messages
