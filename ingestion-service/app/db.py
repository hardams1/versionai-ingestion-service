from __future__ import annotations

import logging
import aiosqlite
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS upload_records (
    ingestion_id TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL,
    filename     TEXT NOT NULL,
    category     TEXT NOT NULL,
    s3_key       TEXT NOT NULL UNIQUE,
    size_bytes   INTEGER NOT NULL DEFAULT 0,
    mime_type    TEXT NOT NULL DEFAULT 'application/octet-stream',
    thumbnail_path TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

CREATE_INDEX_USER = "CREATE INDEX IF NOT EXISTS idx_upload_user ON upload_records(user_id);"
CREATE_INDEX_CAT = "CREATE INDEX IF NOT EXISTS idx_upload_cat ON upload_records(user_id, category);"


async def get_db() -> aiosqlite.Connection:
    settings = get_settings()
    db_path = Path(settings.content_db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(db_path))
    db.row_factory = aiosqlite.Row
    return db


async def init_db() -> None:
    db = await get_db()
    try:
        await db.execute(CREATE_TABLE)
        await db.execute(CREATE_INDEX_USER)
        await db.execute(CREATE_INDEX_CAT)
        await db.commit()
        logger.info("Content index DB initialized at %s", get_settings().content_db_path)
    finally:
        await db.close()


async def insert_record(
    db: aiosqlite.Connection,
    ingestion_id: str,
    user_id: str,
    filename: str,
    category: str,
    s3_key: str,
    size_bytes: int,
    mime_type: str,
    thumbnail_path: str | None = None,
) -> None:
    await db.execute(
        """INSERT OR IGNORE INTO upload_records
           (ingestion_id, user_id, filename, category, s3_key, size_bytes, mime_type, thumbnail_path)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (ingestion_id, user_id, filename, category, s3_key, size_bytes, mime_type, thumbnail_path),
    )
    await db.commit()


async def get_records_by_user(
    db: aiosqlite.Connection,
    user_id: str,
    category: str | None = None,
) -> list[dict]:
    if category:
        cursor = await db.execute(
            "SELECT * FROM upload_records WHERE user_id = ? AND category = ? ORDER BY created_at DESC",
            (user_id, category),
        )
    else:
        cursor = await db.execute(
            "SELECT * FROM upload_records WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_record(db: aiosqlite.Connection, ingestion_id: str) -> dict | None:
    cursor = await db.execute(
        "SELECT * FROM upload_records WHERE ingestion_id = ?", (ingestion_id,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def delete_record(db: aiosqlite.Connection, ingestion_id: str) -> None:
    await db.execute("DELETE FROM upload_records WHERE ingestion_id = ?", (ingestion_id,))
    await db.commit()


async def get_summary_by_user(db: aiosqlite.Connection, user_id: str) -> list[dict]:
    cursor = await db.execute(
        """SELECT category, COUNT(*) as count, SUM(size_bytes) as total_size_bytes
           FROM upload_records WHERE user_id = ?
           GROUP BY category ORDER BY count DESC""",
        (user_id,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]
