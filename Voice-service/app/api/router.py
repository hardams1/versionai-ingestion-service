from fastapi import APIRouter

from app.api.v1.profiles import router as profiles_router
from app.api.v1.synthesize import router as synthesize_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(synthesize_router)
api_router.include_router(profiles_router)
