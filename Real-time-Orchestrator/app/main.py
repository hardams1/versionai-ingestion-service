from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config import get_settings
from app.dependencies import (
    get_brain_client,
    get_session_manager,
    get_video_client,
    get_voice_client,
    get_voice_training_client,
    get_ws_handler,
)
from app.middleware.logging import RequestLoggingMiddleware
from app.models.schemas import ErrorDetail, HealthResponse, ServiceHealth
from app.utils.exceptions import OrchestratorError

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
        "Starting %s v%s [%s] — brain=%s, voice=%s, video=%s",
        settings.app_name, settings.app_version, settings.environment,
        settings.brain_service_url,
        settings.voice_service_url,
        settings.video_avatar_service_url,
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

@app.exception_handler(OrchestratorError)
async def orchestrator_error_handler(_request: Request, exc: OrchestratorError) -> JSONResponse:
    logger.warning("OrchestratorError: %s (code=%s)", exc.detail, exc.code)
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorDetail(detail=exc.detail, code=exc.code).model_dump(),
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(api_router)


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws/orchestrate")
async def ws_orchestrate(
    websocket: WebSocket,
    handler=Depends(get_ws_handler),
) -> None:
    await handler.handle(websocket)


# ---------------------------------------------------------------------------
# Root / health endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    brain = get_brain_client()
    voice = get_voice_client()
    video = get_video_client()
    voice_training = get_voice_training_client()
    session_mgr = get_session_manager()

    checks = await asyncio.gather(
        brain.health(),
        voice.health(),
        video.health(),
        voice_training.health(),
        return_exceptions=True,
    )

    services: dict[str, ServiceHealth] = {}
    for name, result in zip(["brain", "voice", "video_avatar", "voice_training"], checks):
        if isinstance(result, Exception):
            services[name] = ServiceHealth(status="error", detail=str(result))
        else:
            services[name] = ServiceHealth(
                status=result.get("status", "unknown"),
                detail=result.get("detail"),
            )

    all_healthy = all(s.status == "healthy" for s in services.values())

    return HealthResponse(
        status="ok" if all_healthy else "degraded",
        version=settings.app_version,
        environment=settings.environment,
        active_sessions=session_mgr.active_count,
        services=services,
    )


@app.get("/", tags=["system"], include_in_schema=False)
async def root() -> dict:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "websocket": "/ws/orchestrate",
        "endpoints": {
            "orchestrate_http": "/api/v1/orchestrate",
            "orchestrate_ws": "/ws/orchestrate",
            "sessions": "/api/v1/sessions",
            "health": "/health",
        },
    }
