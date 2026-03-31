from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_memory, verify_api_key
from app.models.schemas import ChatMessage, MemoryStatusResponse
from app.services.memory import ConversationMemory

router = APIRouter(prefix="/memory", tags=["memory"], dependencies=[Depends(verify_api_key)])


@router.get("/{conversation_id}", response_model=List[ChatMessage])
async def get_conversation_history(
    conversation_id: str,
    memory: ConversationMemory = Depends(get_memory),
) -> list[ChatMessage]:
    messages = await memory.get_history(conversation_id)
    if not messages:
        raise HTTPException(status_code=404, detail="Conversation not found or empty")
    return messages


@router.get("/{conversation_id}/status", response_model=MemoryStatusResponse)
async def get_conversation_status(
    conversation_id: str,
    memory: ConversationMemory = Depends(get_memory),
) -> MemoryStatusResponse:
    status = await memory.get_status(conversation_id)
    if not status:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return status


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    memory: ConversationMemory = Depends(get_memory),
) -> None:
    deleted = await memory.delete(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
