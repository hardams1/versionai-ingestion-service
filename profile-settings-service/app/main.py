from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.profile import router as profile_router
from app.api.upload import router as upload_router
from app.api.settings import router as settings_router
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
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profile_router)
app.include_router(upload_router)
app.include_router(settings_router)

uploads_dir = Path(settings.local_upload_dir)
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")


@app.on_event("startup")
async def startup():
    logger.info(
        "Starting %s v%s [%s] on port %d",
        settings.app_name, settings.app_version, settings.environment, settings.port,
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
