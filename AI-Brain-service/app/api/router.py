from fastapi import APIRouter

from app.api.v1.chat import router as chat_router
from app.api.v1.memory import router as memory_router
from app.api.v1.personality import router as personality_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(chat_router)
api_router.include_router(personality_router)
api_router.include_router(memory_router)
