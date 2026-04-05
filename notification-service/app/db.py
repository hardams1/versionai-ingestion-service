from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

from app.core.config import get_settings

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS notifications (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL,
    type            TEXT NOT NULL,
    category        TEXT NOT NULL DEFAULT 'system',
    title           TEXT NOT NULL,
    message         TEXT NOT NULL,
    priority        TEXT NOT NULL DEFAULT 'normal',
    status          TEXT NOT NULL DEFAULT 'unread',
    idempotency_key TEXT UNIQUE,
    metadata        TEXT DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_notif_user       ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notif_user_status ON notifications(user_id, status);
CREATE INDEX IF NOT EXISTS idx_notif_idemp      ON notifications(idempotency_key);

CREATE TABLE IF NOT EXISTS notification_preferences (
    user_id                   TEXT PRIMARY KEY,
    follow_notifications      INTEGER NOT NULL DEFAULT 1,
    faq_notifications         INTEGER NOT NULL DEFAULT 1,
    viral_notifications       INTEGER NOT NULL DEFAULT 1,
    ai_evolution_notifications INTEGER NOT NULL DEFAULT 1,
    email_enabled             INTEGER NOT NULL DEFAULT 0,
    push_enabled              INTEGER NOT NULL DEFAULT 1,
    updated_at                TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS threshold_state (
    user_id         TEXT NOT NULL,
    category        TEXT NOT NULL,
    last_threshold  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, category)
);
"""


async def get_db() -> aiosqlite.Connection:
    settings = get_settings()
    db_path = Path(settings.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(db_path))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    return db


async def init_db() -> None:
    db = await get_db()
    try:
        await db.executescript(SCHEMA)
        await db.commit()
        logger.info("Notification DB initialized at %s", get_settings().database_path)
    finally:
        await db.close()
