from fastapi import APIRouter

from app.api.v1.content import router as content_router
from app.api.v1.upload import router as upload_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(upload_router)
api_router.include_router(content_router)
