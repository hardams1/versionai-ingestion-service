from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config import get_settings
from app.dependencies import get_memory, get_personality_store, get_retriever
from app.middleware.logging import RequestLoggingMiddleware
from app.models.schemas import DependencyHealth, ErrorDetail, HealthResponse
from app.utils.exceptions import BrainError

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting %s v%s [%s]", settings.app_name, settings.app_version, settings.environment)

    memory = get_memory()
    await memory.initialize()

    personality_store = get_personality_store()
    await personality_store.initialize(redis_client=memory.redis_client)

    retriever = get_retriever()
    await retriever.initialize()

    logger.info(
        "Ready — LLM=%s, VectorStore=%s, Redis=%s",
        settings.llm_provider,
        settings.vector_store_provider,
        "connected" if memory.is_connected else "disconnected",
    )

    yield

    logger.info("Shutting down %s", settings.app_name)
    await memory.close()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
app.add_middleware(RequestLoggingMiddleware)

cors_kwargs = {
    "allow_origins": settings.cors_origins,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if settings.cors_origins != ["*"]:
    cors_kwargs["allow_credentials"] = True
app.add_middleware(CORSMiddleware, **cors_kwargs)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

@app.exception_handler(BrainError)
async def brain_error_handler(_request: Request, exc: BrainError) -> JSONResponse:
    logger.warning("BrainError: %s (code=%s)", exc.detail, exc.code)
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
    memory = get_memory()
    retriever = get_retriever()

    deps: dict[str, DependencyHealth] = {}

    # Redis check
    t0 = time.perf_counter()
    redis_ok = await memory.health_check()
    redis_ms = (time.perf_counter() - t0) * 1000
    deps["redis"] = DependencyHealth(
        status="healthy" if redis_ok else "unhealthy",
        latency_ms=round(redis_ms, 1),
    )

    # Vector store check
    t0 = time.perf_counter()
    vs_ok = await retriever.health_check()
    vs_ms = (time.perf_counter() - t0) * 1000
    deps["vector_store"] = DependencyHealth(
        status="healthy" if vs_ok else "unhealthy",
        latency_ms=round(vs_ms, 1),
    )

    # Sibling services check (non-blocking, best-effort)
    from app.services.integration import SiblingServiceClient
    sibling_client = SiblingServiceClient(settings)
    for name, check in [("ingestion", sibling_client.check_ingestion), ("processing", sibling_client.check_processing), ("voice", sibling_client.check_voice), ("video_avatar", sibling_client.check_video_avatar)]:
        try:
            result = await check()
            deps[name] = DependencyHealth(
                status=result["status"],
                detail=str(result.get("detail", ""))[:200] if result.get("detail") else None,
            )
        except Exception:
            deps[name] = DependencyHealth(status="error")

    all_ok = all(d.status in ("healthy", "not_configured") for d in deps.values())

    return HealthResponse(
        status="ok" if all_ok else "degraded",
        version=settings.app_version,
        environment=settings.environment,
        llm_provider=settings.llm_provider,
        vector_store=settings.vector_store_provider,
        dependencies=deps,
    )


@app.get("/", tags=["system"], include_in_schema=False)
async def root() -> dict:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
    }
