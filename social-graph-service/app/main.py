from __future__ import annotations

import logging
import traceback
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.access import router as access_router
from app.api.discovery import router as discovery_router
from app.api.follow import router as follow_router
from app.api.profile import router as profile_router
from app.api.requests import router as requests_router
from app.core.config import get_settings
from app.core.database import create_tables
from app.core.redis import close_redis, get_redis

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
        "Starting %s v%s [%s] on port %d",
        settings.app_name, settings.app_version, settings.environment, settings.port,
    )
    await create_tables()
    logger.info("Database tables ready")
    try:
        await get_redis()
    except Exception as exc:
        logger.warning("Redis not available: %s — rate limiting disabled", exc)
    yield
    await close_redis()
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
    logger.debug(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {type(exc).__name__}: {exc}"},
    )


app.include_router(profile_router)
app.include_router(follow_router)
app.include_router(requests_router)
app.include_router(access_router)
app.include_router(discovery_router)


@app.get("/health", tags=["system"])
async def health():
    redis_ok = False
    try:
        r = await get_redis()
        await r.ping()
        redis_ok = True
    except Exception:
        pass

    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "port": settings.port,
        "redis": "connected" if redis_ok else "unavailable",
    }
