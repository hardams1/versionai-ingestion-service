from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

import aiosqlite

from app.models.enums import FileCategory, ProcessingStatus
from app.models.schemas import ProcessingRecord

logger = logging.getLogger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS processing_records (
    ingestion_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    file_category TEXT NOT NULL,
    filename TEXT NOT NULL,
    chunks_count INTEGER DEFAULT 0,
    embeddings_count INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    duration_seconds REAL
)
"""


class StateStore:
    """SQLite-backed idempotency and status tracking."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute(_CREATE_TABLE)
        await self._db.commit()
        logger.info("State store initialized at %s", self._db_path)

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    async def is_processed(self, ingestion_id: str) -> bool:
        assert self._db is not None
        async with self._lock:
            cursor = await self._db.execute(
                "SELECT status FROM processing_records WHERE ingestion_id = ?",
                (ingestion_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return False
            return row["status"] == ProcessingStatus.COMPLETED

    async def get_record(self, ingestion_id: str) -> ProcessingRecord | None:
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT * FROM processing_records WHERE ingestion_id = ?",
            (ingestion_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return ProcessingRecord(
            ingestion_id=row["ingestion_id"],
            status=ProcessingStatus(row["status"]),
            file_category=FileCategory(row["file_category"]),
            filename=row["filename"],
            chunks_count=row["chunks_count"],
            embeddings_count=row["embeddings_count"],
            error_message=row["error_message"],
            started_at=datetime.fromisoformat(row["started_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            duration_seconds=row["duration_seconds"],
        )

    async def upsert(self, record: ProcessingRecord) -> None:
        assert self._db is not None
        async with self._lock:
            await self._db.execute(
                """
                INSERT INTO processing_records
                    (ingestion_id, status, file_category, filename, chunks_count,
                     embeddings_count, error_message, started_at, completed_at, duration_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ingestion_id) DO UPDATE SET
                    status = excluded.status,
                    chunks_count = excluded.chunks_count,
                    embeddings_count = excluded.embeddings_count,
                    error_message = excluded.error_message,
                    completed_at = excluded.completed_at,
                    duration_seconds = excluded.duration_seconds
                """,
                (
                    record.ingestion_id,
                    record.status.value,
                    record.file_category.value,
                    record.filename,
                    record.chunks_count,
                    record.embeddings_count,
                    record.error_message,
                    record.started_at.isoformat(),
                    record.completed_at.isoformat() if record.completed_at else None,
                    record.duration_seconds,
                ),
            )
            await self._db.commit()

    async def list_recent(self, limit: int = 50) -> list[ProcessingRecord]:
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT * FROM processing_records ORDER BY started_at DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [
            ProcessingRecord(
                ingestion_id=r["ingestion_id"],
                status=ProcessingStatus(r["status"]),
                file_category=FileCategory(r["file_category"]),
                filename=r["filename"],
                chunks_count=r["chunks_count"],
                embeddings_count=r["embeddings_count"],
                error_message=r["error_message"],
                started_at=datetime.fromisoformat(r["started_at"]),
                completed_at=datetime.fromisoformat(r["completed_at"]) if r["completed_at"] else None,
                duration_seconds=r["duration_seconds"],
            )
            for r in rows
        ]

    async def count_by_status(self) -> dict[str, int]:
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT status, COUNT(*) as cnt FROM processing_records GROUP BY status"
        )
        rows = await cursor.fetchall()
        return {r["status"]: r["cnt"] for r in rows}
