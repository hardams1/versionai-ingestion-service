from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.dependencies import (
    get_orchestrator,
    get_sqs_consumer,
    get_state_store,
    get_vector_store,
)
from app.middleware.logging import RequestLoggingMiddleware
from app.models.enums import ProcessingStatus
from app.models.schemas import (
    ErrorDetail,
    HealthResponse,
    ProcessingStatusResponse,
)
from app.utils.exceptions import ProcessingError
from app.worker import Worker

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

_worker: Worker | None = None
_worker_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global _worker, _worker_task

    logger.info("Starting %s v%s [%s]", settings.app_name, settings.app_version, settings.environment)

    state_store = get_state_store()
    await state_store.initialize()

    vector_store = get_vector_store()
    await vector_store.initialize()

    consumer = get_sqs_consumer()
    try:
        orchestrator = get_orchestrator()
    except Exception:
        logger.exception(
            "Failed to build orchestrator — worker will NOT start. "
            "Check EMBEDDING_PROVIDER / OPENAI_API_KEY configuration."
        )
        yield
        await state_store.close()
        return

    _worker = Worker(
        consumer=consumer,
        orchestrator=orchestrator,
        concurrency=settings.worker_concurrency,
        shutdown_timeout=settings.worker_shutdown_timeout,
    )
    _worker_task = asyncio.create_task(_worker.start())
    logger.info("Worker task launched")

    yield

    logger.info("Shutting down %s", settings.app_name)
    if _worker:
        await _worker.stop()
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass

    await state_store.close()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ProcessingError)
async def processing_error_handler(_request: Request, exc: ProcessingError) -> JSONResponse:
    logger.warning("ProcessingError: %s (code=%s)", exc.detail, exc.code)
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorDetail(detail=exc.detail, code=exc.code).model_dump(),
    )


# ---------------------------------------------------------------------------
# Health & Status endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(
        version=settings.app_version,
        environment=settings.environment,
        worker_running=_worker.is_running if _worker else False,
        messages_processed=_worker.messages_processed if _worker else 0,
    )


@app.get("/", tags=["system"], include_in_schema=False)
async def root() -> dict:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
    }


@app.post("/api/v1/process", tags=["processing"], status_code=202)
async def trigger_processing(payload: dict) -> dict:
    """
    Accept a QueueMessage directly via HTTP (used when SQS is unavailable).
    This lets the ingestion service push messages without infrastructure.
    """
    from app.models.schemas import QueueMessage

    try:
        message = QueueMessage(**payload)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid message: {exc}")

    if not _worker or not _worker.is_running:
        raise HTTPException(status_code=503, detail="Worker not running")

    orchestrator = get_orchestrator()
    record = await orchestrator.process(message)
    return {
        "ingestion_id": record.ingestion_id,
        "status": record.status.value,
        "chunks_count": record.chunks_count,
        "embeddings_count": record.embeddings_count,
        "error_message": record.error_message,
    }


@app.get("/api/v1/status/{ingestion_id}", response_model=ProcessingStatusResponse, tags=["status"])
async def get_processing_status(ingestion_id: str) -> ProcessingStatusResponse:
    state_store = get_state_store()
    record = await state_store.get_record(ingestion_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Ingestion ID not found")
    return ProcessingStatusResponse(
        ingestion_id=record.ingestion_id,
        status=record.status,
        chunks_count=record.chunks_count,
        embeddings_count=record.embeddings_count,
        error_message=record.error_message,
        started_at=record.started_at,
        completed_at=record.completed_at,
        duration_seconds=record.duration_seconds,
    )


@app.get("/api/v1/status", tags=["status"])
async def list_processing_status(limit: int = 50) -> dict:
    state_store = get_state_store()
    records = await state_store.list_recent(limit)
    counts = await state_store.count_by_status()
    return {
        "records": [
            ProcessingStatusResponse(
                ingestion_id=r.ingestion_id,
                status=r.status,
                chunks_count=r.chunks_count,
                embeddings_count=r.embeddings_count,
                error_message=r.error_message,
                started_at=r.started_at,
                completed_at=r.completed_at,
                duration_seconds=r.duration_seconds,
            )
            for r in records
        ],
        "counts": counts,
        "total": sum(counts.values()),
    }


@app.get("/api/v1/metrics", tags=["system"])
async def metrics() -> dict:
    state_store = get_state_store()
    counts = await state_store.count_by_status()
    return {
        "worker_running": _worker.is_running if _worker else False,
        "messages_processed": _worker.messages_processed if _worker else 0,
        "status_counts": counts,
    }
