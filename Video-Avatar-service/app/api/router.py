from fastapi import APIRouter

from app.api.v1.avatars import router as avatars_router
from app.api.v1.generate import router as generate_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(generate_router)
api_router.include_router(avatars_router)
