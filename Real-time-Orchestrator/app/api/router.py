from fastapi import APIRouter

from app.api.v1.orchestrate import router as orchestrate_router
from app.api.v1.sessions import router as sessions_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(orchestrate_router)
api_router.include_router(sessions_router)
