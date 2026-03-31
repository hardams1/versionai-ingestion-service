from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config import get_settings
from app.middleware.logging import RequestLoggingMiddleware
from app.models.schemas import ErrorDetail, HealthResponse
from app.utils.exceptions import VideoAvatarError

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "Starting %s v%s [%s] — renderer: %s",
        settings.app_name, settings.app_version,
        settings.environment, settings.renderer_provider,
    )
    yield
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

@app.exception_handler(VideoAvatarError)
async def video_avatar_error_handler(_request: Request, exc: VideoAvatarError) -> JSONResponse:
    logger.warning("VideoAvatarError: %s (code=%s)", exc.detail, exc.code)
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorDetail(detail=exc.detail, code=exc.code).model_dump(),
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(api_router)


# ---------------------------------------------------------------------------
# Root endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(
        version=settings.app_version,
        environment=settings.environment,
        renderer_provider=settings.renderer_provider,
    )


@app.get("/", tags=["system"], include_in_schema=False)
async def root() -> dict:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "renderer_provider": settings.renderer_provider,
        "docs": "/docs",
    }
