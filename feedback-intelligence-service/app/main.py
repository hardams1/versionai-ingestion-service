from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import engine
from app.models.base import Base
from app.services.categorization_service import CategorizationService
from app.services.faq_service import FaqService
from app.services.ranking_service import RankingService

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

categorization_service = CategorizationService(settings)
ranking_service = RankingService(settings)
faq_service = FaqService(ranking_service)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ensured")

    await ranking_service.initialize()

    yield

    await ranking_service.close()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.feedback import router as feedback_router
from app.api.faq import router as faq_router

app.include_router(feedback_router)
app.include_router(faq_router)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
    }


@app.get("/", include_in_schema=False)
async def root():
    return {"service": settings.app_name, "version": settings.app_version}
