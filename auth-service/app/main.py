from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.onboarding import router as onboarding_router
from app.core.config import get_settings
from app.core.database import create_tables

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(onboarding_router)


@app.on_event("startup")
async def startup():
    logger.info(
        "Starting %s v%s [%s]",
        settings.app_name, settings.app_version, settings.environment,
    )
    await create_tables()
    logger.info("Database tables ready")


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": settings.app_version,
        "environment": settings.environment,
    }
